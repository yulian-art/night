// Copyright 向星而行. In-game HUD (pure C++ Slate; no UMG assets).
#include "StarHudWidget.h"

#include "Styling/CoreStyle.h"
#include "Styling/SlateColor.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Text/STextBlock.h"

void SStarHudWidget::Construct(const FArguments& InArgs)
{
	const FSlateFontInfo TitleFont = FCoreStyle::GetDefaultFontStyle("Bold", 16);
	const FSlateFontInfo BodyFont = FCoreStyle::GetDefaultFontStyle("Regular", 14);

	// 设计文档要求「深蓝半透明底、暖金强调」，这里直接用同一套观感。
	const FLinearColor PanelColor(0.02f, 0.05f, 0.12f, 0.72f);
	const FLinearColor Gold(1.0f, 0.82f, 0.55f, 1.0f);
	const FLinearColor Pale(0.86f, 0.91f, 0.92f, 1.0f);

	ChildSlot
	[
		SNew(SOverlay)

		// ---- 左上角状态面板 ----
		+ SOverlay::Slot()
		.HAlign(HAlign_Left)
		.VAlign(VAlign_Top)
		.Padding(FMargin(24.0f))
		[
			SNew(SBorder)
			.BorderBackgroundColor(PanelColor)
			.Padding(FMargin(18.0f, 14.0f))
			[
				SNew(SVerticalBox)

				+ SVerticalBox::Slot()
				.AutoHeight()
				.Padding(FMargin(0.0f, 2.0f))
				[
					SAssignNew(StarlightText, STextBlock)
					.Font(TitleFont)
					.ColorAndOpacity(FSlateColor(Gold))
				]

				+ SVerticalBox::Slot()
				.AutoHeight()
				.Padding(FMargin(0.0f, 2.0f))
				[
					SAssignNew(TaskText, STextBlock)
					.Font(BodyFont)
					.ColorAndOpacity(FSlateColor(Pale))
				]

				// 动作 = 色块（图标）+ 文字。设计文档明确要求提示不能只靠颜色，
				// 所以色块只是辅助，动作名称必须作为文字出现。
				+ SVerticalBox::Slot()
				.AutoHeight()
				.Padding(FMargin(0.0f, 6.0f))
				[
					SNew(SHorizontalBox)

					+ SHorizontalBox::Slot()
					.AutoWidth()
					.VAlign(VAlign_Center)
					.Padding(FMargin(0.0f, 0.0f, 8.0f, 0.0f))
					[
						SNew(SBox)
						.WidthOverride(18.0f)
						.HeightOverride(18.0f)
						[
							SAssignNew(ActionSwatch, SBorder)
							.BorderBackgroundColor(TAttribute<FSlateColor>::CreateLambda(
								[this]() { return FSlateColor(SwatchColor); }))
							.Padding(FMargin(0.0f))
							[
								// SBorder 靠自身背景色充当图标；子节点只用于撑出尺寸。
								SNew(STextBlock).Text(FText::GetEmpty())
							]
						]
					]

					+ SHorizontalBox::Slot()
					.AutoWidth()
					.VAlign(VAlign_Center)
					[
						SAssignNew(ActionText, STextBlock)
						.Font(BodyFont)
						.ColorAndOpacity(FSlateColor(Pale))
					]
				]

				+ SVerticalBox::Slot()
				.AutoHeight()
				.Padding(FMargin(0.0f, 2.0f))
				[
					SAssignNew(TrackingText, STextBlock)
					.Font(BodyFont)
					.ColorAndOpacity(FSlateColor(Pale))
				]

				+ SVerticalBox::Slot()
				.AutoHeight()
				.Padding(FMargin(0.0f, 6.0f))
				[
					SAssignNew(HintText, STextBlock)
					.Font(TitleFont)
					.ColorAndOpacity(FSlateColor(Gold))
				]
			]
		]

		// ---- 暂停遮罩（居中）----
		+ SOverlay::Slot()
		.HAlign(HAlign_Center)
		.VAlign(VAlign_Center)
		[
			SAssignNew(PausePanel, SBorder)
			.Visibility(TAttribute<EVisibility>::CreateLambda(
				[this]() { return bPaused ? EVisibility::Visible : EVisibility::Collapsed; }))
			.BorderBackgroundColor(FLinearColor(0.02f, 0.05f, 0.12f, 0.85f))
			.Padding(FMargin(28.0f, 18.0f))
			[
				SAssignNew(PauseText, STextBlock)
				.Font(TitleFont)
				.ColorAndOpacity(FSlateColor(Gold))
			]
		]
	];
}

void SStarHudWidget::Refresh(const FStarHudState& State)
{
	if (StarlightText.IsValid())
	{
		StarlightText->SetText(FText::FromString(FString::Printf(TEXT("星光 %d"), State.Starlight)));
	}
	if (TaskText.IsValid())
	{
		TaskText->SetText(FText::FromString(
			FString::Printf(TEXT("任务 %d/%d"), State.CompletedTasks, State.TotalTasks)));
	}
	if (ActionText.IsValid())
	{
		ActionText->SetText(FText::FromString(
			FString::Printf(TEXT("动作 %s"), *ActionToText(State.CurrentAction).ToString())));
	}
	if (TrackingText.IsValid())
	{
		TrackingText->SetText(FText::FromString(
			FString::Printf(TEXT("状态 %s"), *TrackingToText(State.Tracking).ToString())));
	}
	if (HintText.IsValid())
	{
		HintText->SetText(BuildHint(State));
	}
	if (PauseText.IsValid())
	{
		PauseText->SetText(FText::FromString(TEXT("已暂停 · 按 Esc 继续")));
	}

	// Picked up by the Slate attributes on the next paint.
	SwatchColor = ActionToColor(State.CurrentAction);
	bPaused = State.bPaused;
}

FText SStarHudWidget::BuildHint(const FStarHudState& State)
{
	if (State.bLevelComplete)
	{
		return FText::FromString(TEXT("本关完成 · 星种已获得"));
	}
	if (State.bWaitingAtStation)
	{
		// 任务点提示必须点名动作，玩家才知道要做什么。
		if (State.RequiredAction != EStarAction::None)
		{
			return FText::FromString(FString::Printf(
				TEXT("请做：%s"), *ActionToText(State.RequiredAction).ToString()));
		}
		return FText::FromString(TEXT("在任务点等待"));
	}
	if (State.Tracking == EStarTracking::Lost)
	{
		return FText::FromString(TEXT("看不到你 · 请回到画面中央"));
	}
	if (State.Tracking != EStarTracking::Ready)
	{
		return FText::FromString(TEXT("回中站稳"));
	}
	return FText::FromString(TEXT("前进中"));
}

FText SStarHudWidget::ActionToText(EStarAction Action)
{
	switch (Action)
	{
	case EStarAction::Squat:        return FText::FromString(TEXT("蹲下"));
	case EStarAction::LeftLeg:      return FText::FromString(TEXT("抬左腿"));
	case EStarAction::RightLeg:     return FText::FromString(TEXT("抬右腿"));
	case EStarAction::JumpLeft:     return FText::FromString(TEXT("往左跳"));
	case EStarAction::JumpRight:    return FText::FromString(TEXT("往右跳"));
	case EStarAction::JumpingJack:  return FText::FromString(TEXT("开合跳"));
	default:                        return FText::FromString(TEXT("-"));
	}
}

FText SStarHudWidget::TrackingToText(EStarTracking State)
{
	switch (State)
	{
	case EStarTracking::Ready:      return FText::FromString(TEXT("READY"));
	case EStarTracking::NotReady:   return FText::FromString(TEXT("NOT_READY"));
	case EStarTracking::Lost:       return FText::FromString(TEXT("LOST"));
	default:                        return FText::FromString(TEXT("-"));
	}
}

FLinearColor SStarHudWidget::ActionToColor(EStarAction Action)
{
	// Distinct hues per action so the icon reads at a glance; the text beside it
	// remains the authoritative cue.
	switch (Action)
	{
	case EStarAction::Squat:        return FLinearColor(0.45f, 0.70f, 0.85f, 1.0f);
	case EStarAction::LeftLeg:      return FLinearColor(0.55f, 0.85f, 0.60f, 1.0f);
	case EStarAction::RightLeg:     return FLinearColor(0.35f, 0.65f, 0.45f, 1.0f);
	case EStarAction::JumpLeft:     return FLinearColor(0.95f, 0.75f, 0.40f, 1.0f);
	case EStarAction::JumpRight:    return FLinearColor(0.95f, 0.55f, 0.30f, 1.0f);
	case EStarAction::JumpingJack:  return FLinearColor(1.00f, 0.82f, 0.55f, 1.0f);
	default:                        return FLinearColor(0.35f, 0.35f, 0.40f, 1.0f);
	}
}
