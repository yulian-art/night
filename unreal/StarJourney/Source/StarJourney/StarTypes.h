// Copyright 向星而行. Domain types mirroring proto/star/v1/star.proto.
#pragma once

#include "CoreMinimal.h"
#include "StarTypes.generated.h"

// Body actions. Numeric values match star.v1.Action exactly so the WebSocket
// gateway's string names map 1:1.
UENUM(BlueprintType)
enum class EStarAction : uint8
{
	None			= 0,
	Squat			= 1,	// 蹲下：穿过低树枝/花藤/云拱门
	LeftLeg			= 2,	// 抬左腿：跨过左脚侧障碍、触发脚印机关
	RightLeg		= 3,	// 抬右腿：跨过右脚侧障碍、触发脚印机关
	JumpLeft		= 4,	// 往左跳：向相邻左道换道
	JumpRight		= 5,	// 往右跳：向相邻右道换道
	JumpingJack		= 6,	// 开合跳：越过缺口、点亮机关、唤醒星种
};

// Cycle phase. Values match star.v1.Phase.
UENUM(BlueprintType)
enum class EStarPhase : uint8
{
	None		= 0,
	Begin		= 1,	// 动作开始：抬腿/跳跃立即反馈，蹲下开始俯身
	Complete	= 2,	// 完成：机关此刻推进，计一次
	Cancel		= 3,	// 取消：周期作废（如追踪丢失），不计为站立
};

// Human tracking state. Values match star.v1.TrackingState.
UENUM(BlueprintType)
enum class EStarTracking : uint8
{
	None		= 0,
	Lost		= 1,	// 相机看不到人
	NotReady	= 2,	// 未就绪/需重新站稳
	Ready		= 3,	// 真人回到中央站稳，可准备下一动作
};

// One input event. Either an action event or a tracking event, never both.
// Mirrors star.v1.InputEvent. Generation arrives as a string over the wire
// because JSON numbers cannot hold a full uint64; it is parsed with
// FCString::Strtoui64.
//
// int64 rather than uint64: UnrealHeaderTool rejects uint64 in reflected
// Blueprint properties and functions. A Unix-nanosecond timestamp stays
// positive in int64 until year 2262, so range is not a practical constraint.
USTRUCT(BlueprintType)
struct FStarInputEvent
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Star")
	int64 Generation = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Star")
	EStarAction Action = EStarAction::None;

	UPROPERTY(BlueprintReadOnly, Category = "Star")
	EStarPhase Phase = EStarPhase::None;

	UPROPERTY(BlueprintReadOnly, Category = "Star")
	EStarTracking Tracking = EStarTracking::None;

	bool IsAction() const { return Action != EStarAction::None; }
	bool IsTracking() const { return Tracking != EStarTracking::None; }

	static EStarAction ActionFromString(const FString& S)
	{
		if (S == TEXT("SQUAT"))        return EStarAction::Squat;
		if (S == TEXT("LEFT_LEG"))     return EStarAction::LeftLeg;
		if (S == TEXT("RIGHT_LEG"))    return EStarAction::RightLeg;
		if (S == TEXT("JUMP_LEFT"))    return EStarAction::JumpLeft;
		if (S == TEXT("JUMP_RIGHT"))   return EStarAction::JumpRight;
		if (S == TEXT("JUMPING_JACK")) return EStarAction::JumpingJack;
		return EStarAction::None;
	}
	static EStarPhase PhaseFromString(const FString& S)
	{
		if (S == TEXT("BEGIN"))    return EStarPhase::Begin;
		if (S == TEXT("COMPLETE")) return EStarPhase::Complete;
		if (S == TEXT("CANCEL"))   return EStarPhase::Cancel;
		return EStarPhase::None;
	}
	static EStarTracking TrackingFromString(const FString& S)
	{
		if (S == TEXT("LOST"))       return EStarTracking::Lost;
		if (S == TEXT("NOT_READY"))  return EStarTracking::NotReady;
		if (S == TEXT("READY"))      return EStarTracking::Ready;
		return EStarTracking::None;
	}
};

// Lane index for the three-lane runner: 0 = left, 1 = center, 2 = right.
UENUM(BlueprintType)
enum class EStarLane : uint8
{
	Left	= 0,
	Center	= 1,
	Right	= 2,
};
