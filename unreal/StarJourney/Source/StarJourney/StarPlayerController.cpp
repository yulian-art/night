// Copyright 向星而行. Player controller: Esc toggles the pause.
#include "StarPlayerController.h"

#include "Components/InputComponent.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"

AStarPlayerController::AStarPlayerController()
{
	// 暂停时控制器默认只做最小更新，输入路径不会完整执行；
	// 仅设置 InputComponent->bExecuteWhenPaused 是不够的，两者配合 Esc 才能在暂停后继续生效。
	bShouldPerformFullTickWhenPaused = true;
}

void AStarPlayerController::SetupInputComponent()
{
	Super::SetupInputComponent();

	// 暂停时输入组件默认被跳过；不设这一项，Esc 只能暂停、永远无法恢复。
	if (InputComponent)
	{
		InputComponent->bExecuteWhenPaused = true;
		InputComponent->BindKey(EKeys::Escape, IE_Pressed, this, &AStarPlayerController::TogglePause);
	}
}

void AStarPlayerController::TogglePause()
{
	UGameplayStatics::SetGamePaused(this, !UGameplayStatics::IsGamePaused(this));
}
