// Copyright 向星而行. Durable outbox for completed runs (UE port of client/savequeue).
#include "StarSaveQueueComponent.h"

#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"

UStarSaveQueueComponent::UStarSaveQueueComponent()
{
	// No per-frame work; everything is event driven (HTTP responses).
	PrimaryComponentTick.bCanEverTick = false;
}

void UStarSaveQueueComponent::BeginPlay()
{
	Super::BeginPlay();

	if (!LoadPending())
	{
		// Corrupt list: keep the bytes for inspection and start empty rather
		// than overwriting history.
		UE_LOG(LogTemp, Error,
			TEXT("StarJourney: pending run list is corrupt; it was left on disk untouched"));
	}

	// Retry anything left over from a previous session, then refresh progress.
	if (Pending.Num() > 0)
	{
		Flush();
	}
	FetchProgress();
}

FString UStarSaveQueueComponent::ResolvePath() const
{
	FString Path = PendingFileName;
	if (FPaths::IsRelative(Path))
	{
		Path = FPaths::ProjectSavedDir() / Path;
	}
	return FPaths::ConvertRelativePathToFull(Path);
}

bool UStarSaveQueueComponent::LoadPending()
{
	Pending.Reset();

	const FString Path = ResolvePath();
	FString Content;
	if (!FFileHelper::LoadFileToString(Content, *Path))
	{
		// A missing file is a valid, empty queue; a read failure is not.
		return !IFileManager::Get().FileExists(*Path);
	}

	TArray<TSharedPtr<FJsonValue>> Array;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Content);
	if (!FJsonSerializer::Deserialize(Reader, Array))
	{
		return false;
	}

	for (const TSharedPtr<FJsonValue>& Value : Array)
	{
		const TSharedPtr<FJsonObject>* Object = nullptr;
		if (!Value.IsValid() || !Value->TryGetObject(Object) || Object == nullptr)
		{
			return false;
		}
		FStarRun Run;
		if (!(*Object)->TryGetStringField(TEXT("run_id"), Run.RunId) || Run.RunId.IsEmpty())
		{
			return false;
		}
		// JSON numbers arrive as double; these fields stay far below 2^53 in
		// practice, so the cast is exact.
		double Number = 0.0;
		if ((*Object)->TryGetNumberField(TEXT("level_id"), Number)) { Run.LevelId = (int32)Number; }
		if ((*Object)->TryGetNumberField(TEXT("score"), Number)) { Run.Score = (int64)Number; }
		if ((*Object)->TryGetNumberField(TEXT("active_ms"), Number)) { Run.ActiveMs = (int64)Number; }

		const TSharedPtr<FJsonObject>* Counts = nullptr;
		if ((*Object)->TryGetObjectField(TEXT("action_counts"), Counts) && Counts != nullptr)
		{
			for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*Counts)->Values)
			{
				if (Pair.Value.IsValid())
				{
					Run.ActionCounts.Add(FCString::Atoi(*Pair.Key), (int64)Pair.Value->AsNumber());
				}
			}
		}
		Pending.Add(Run);
	}
	return true;
}

bool UStarSaveQueueComponent::Enqueue(const FStarRun& Run)
{
	if (Run.RunId.IsEmpty())
	{
		return false;
	}
	for (const FStarRun& Existing : Pending)
	{
		if (Existing.RunId == Run.RunId)
		{
			// Already queued; the server is idempotent on run_id anyway.
			return true;
		}
	}

	TArray<FStarRun> Next = Pending;
	Next.Add(Run);
	// Persist BEFORE any send, so a crash or a lost reply cannot lose the run.
	if (!WriteAtomic(Next))
	{
		return false;
	}
	Pending = Next;
	return true;
}

void UStarSaveQueueComponent::Flush()
{
	if (bFlushActive)
	{
		return;
	}
	bFlushActive = true;
	SendNext();
}

FString UStarSaveQueueComponent::BuildRunJson(const FStarRun& Run) const
{
	FString Body;
	const TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
		TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Body);
	Writer->WriteObjectStart();
	Writer->WriteValue(TEXT("run_id"), Run.RunId);
	Writer->WriteValue(TEXT("level_id"), Run.LevelId);
	Writer->WriteValue(TEXT("score"), Run.Score);
	Writer->WriteValue(TEXT("active_ms"), Run.ActiveMs);
	Writer->WriteObjectStart(TEXT("action_counts"));
	for (const TPair<int32, int64>& Pair : Run.ActionCounts)
	{
		Writer->WriteValue(FString::FromInt(Pair.Key), Pair.Value);
	}
	Writer->WriteObjectEnd();
	Writer->WriteObjectEnd();
	Writer->Close();
	return Body;
}

void UStarSaveQueueComponent::SendNext()
{
	if (!Pending.IsValidIndex(0))
	{
		// Queue drained: this pass succeeded.
		bFlushActive = false;
		InFlightRunId.Reset();
		OnFlushFinished.Broadcast(true);
		return;
	}

	const FStarRun& Run = Pending[0];
	InFlightRunId = Run.RunId;

	const TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
	Request->SetURL(ServiceBaseUrl + TEXT("/api/save"));
	Request->SetVerb(TEXT("POST"));
	Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
	Request->SetContentAsString(BuildRunJson(Run));
	Request->OnProcessRequestComplete().BindUObject(this, &UStarSaveQueueComponent::OnSaveResponse);
	Request->ProcessRequest();
}

void UStarSaveQueueComponent::OnSaveResponse(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bConnectedSuccessfully)
{
	// Any failure keeps the head record and ends this pass; the caller may
	// flush again later (next station, next launch).
	if (!bConnectedSuccessfully || !Response.IsValid() || Response->GetResponseCode() != 200)
	{
		bFlushActive = false;
		InFlightRunId.Reset();
		OnFlushFinished.Broadcast(false);
		return;
	}

	// Accept the acknowledgement only if the server echoes the same run_id.
	FString AckId;
	TSharedPtr<FJsonObject> Body;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Response->GetContentAsString());
	if (FJsonSerializer::Deserialize(Reader, Body) && Body.IsValid())
	{
		const TSharedPtr<FJsonObject>* RunObject = nullptr;
		if (Body->TryGetObjectField(TEXT("run"), RunObject) && RunObject != nullptr)
		{
			(*RunObject)->TryGetStringField(TEXT("run_id"), AckId);
		}
	}
	if (AckId.IsEmpty() || AckId != InFlightRunId)
	{
		bFlushActive = false;
		InFlightRunId.Reset();
		OnFlushFinished.Broadcast(false);
		return;
	}

	// Confirmed: persist the reduced list before sending the next record, so a
	// crash here cannot resurrect an already-acknowledged run.
	const TArray<FStarRun> Next = Pending.RightChop(1);
	if (!WriteAtomic(Next))
	{
		bFlushActive = false;
		InFlightRunId.Reset();
		OnFlushFinished.Broadcast(false);
		return;
	}
	Pending = Next;
	SendNext();
}

void UStarSaveQueueComponent::FetchProgress()
{
	if (bProgressRequestActive)
	{
		return;
	}
	bProgressRequestActive = true;

	const TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
	Request->SetURL(ServiceBaseUrl + TEXT("/api/progress"));
	Request->SetVerb(TEXT("GET"));
	Request->OnProcessRequestComplete().BindUObject(this, &UStarSaveQueueComponent::OnProgressResponse);
	Request->ProcessRequest();
}

void UStarSaveQueueComponent::OnProgressResponse(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bConnectedSuccessfully)
{
	bProgressRequestActive = false;

	if (!bConnectedSuccessfully || !Response.IsValid() || Response->GetResponseCode() != 200)
	{
		OnProgressLoaded.Broadcast(false);
		return;
	}

	TSharedPtr<FJsonObject> Body;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Response->GetContentAsString());
	if (!FJsonSerializer::Deserialize(Reader, Body) || !Body.IsValid())
	{
		OnProgressLoaded.Broadcast(false);
		return;
	}

	const TArray<TSharedPtr<FJsonValue>>* Levels = nullptr;
	if (!Body->TryGetArrayField(TEXT("levels"), Levels) || Levels == nullptr)
	{
		OnProgressLoaded.Broadcast(false);
		return;
	}

	Progress.Reset();
	for (const TSharedPtr<FJsonValue>& Value : *Levels)
	{
		const TSharedPtr<FJsonObject>* LevelObject = nullptr;
		if (!Value.IsValid() || !Value->TryGetObject(LevelObject) || LevelObject == nullptr)
		{
			continue;
		}
		FStarLevelProgress Entry;
		double Number = 0.0;
		if ((*LevelObject)->TryGetNumberField(TEXT("level_id"), Number)) { Entry.LevelId = (int32)Number; }
		(*LevelObject)->TryGetBoolField(TEXT("completed"), Entry.bCompleted);
		if ((*LevelObject)->TryGetNumberField(TEXT("best_score"), Number)) { Entry.BestScore = (int64)Number; }
		(*LevelObject)->TryGetBoolField(TEXT("unlocked"), Entry.bUnlocked);
		Progress.Add(Entry);
	}
	OnProgressLoaded.Broadcast(true);
}

bool UStarSaveQueueComponent::WriteAtomic(const TArray<FStarRun>& Runs)
{
	const FString Path = ResolvePath();
	const FString Directory = FPaths::GetPath(Path);
	if (!IFileManager::Get().MakeDirectory(*Directory, /*Tree=*/true))
	{
		return false;
	}

	// Serialize first: a serialization failure must not truncate the live file.
	FString Serialized;
	{
		const TSharedRef<TJsonWriter<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>> Writer =
			TJsonWriterFactory<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>::Create(&Serialized);
		Writer->WriteArrayStart();
		for (const FStarRun& Run : Runs)
		{
			Writer->WriteObjectStart();
			Writer->WriteValue(TEXT("run_id"), Run.RunId);
			Writer->WriteValue(TEXT("level_id"), Run.LevelId);
			Writer->WriteValue(TEXT("score"), Run.Score);
			Writer->WriteValue(TEXT("active_ms"), Run.ActiveMs);
			Writer->WriteObjectStart(TEXT("action_counts"));
			for (const TPair<int32, int64>& Pair : Run.ActionCounts)
			{
				Writer->WriteValue(FString::FromInt(Pair.Key), Pair.Value);
			}
			Writer->WriteObjectEnd();
			Writer->WriteObjectEnd();
		}
		Writer->WriteArrayEnd();
		Writer->Close();
	}

	// Write a sibling temp file, close it, then replace the target in one step:
	// a concurrent reader sees either the old list or the new one, never a
	// half-written file. (No directory fsync, so power-loss atomicity is not
	// promised - the same caveat the Go implementation documents.)
	const FString TempPath = Path + TEXT(".tmp");
	{
		TUniquePtr<FArchive> Archive(IFileManager::Get().CreateFileWriter(*TempPath));
		if (!Archive)
		{
			return false;
		}
		const FTCHARToUTF8 Utf8(*Serialized);
		Archive->Serialize(const_cast<ANSICHAR*>(Utf8.Get()), Utf8.Length());
		Archive->Flush();
		Archive->Close();
	}
	return IFileManager::Get().Move(*Path, *TempPath, /*bReplace=*/true);
}
