// Copyright 向星而行. Primary game module.
#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

class FStarJourneyModule : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
};
