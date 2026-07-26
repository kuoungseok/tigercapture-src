#include "TigerStudioButton.h"

#include "TigerStudioGeneratedWidget.h"

void UTigerStudioButton::InitializeTigerButton(UTigerStudioGeneratedWidget* InOwner)
{
    TigerOwner = InOwner;
    OnClicked.AddUniqueDynamic(this, &UTigerStudioButton::HandleClicked);
    OnHovered.AddUniqueDynamic(this, &UTigerStudioButton::HandleHovered);
    OnUnhovered.AddUniqueDynamic(this, &UTigerStudioButton::HandleUnhovered);
    OnPressed.AddUniqueDynamic(this, &UTigerStudioButton::HandlePressed);
    OnReleased.AddUniqueDynamic(this, &UTigerStudioButton::HandleReleased);
}

void UTigerStudioButton::HandleClicked()
{
    if (TigerOwner)
    {
        TigerOwner->ExecuteTigerInteraction(TigerComponentId, TEXT("clicked"));
    }
}

void UTigerStudioButton::HandleHovered()
{
    if (TigerOwner)
    {
        TigerOwner->ExecuteTigerInteraction(TigerComponentId, TEXT("hovered"));
    }
}

void UTigerStudioButton::HandleUnhovered()
{
    if (TigerOwner)
    {
        TigerOwner->ExecuteTigerInteraction(TigerComponentId, TEXT("unhovered"));
    }
}

void UTigerStudioButton::HandlePressed()
{
    if (TigerOwner)
    {
        TigerOwner->ExecuteTigerInteraction(TigerComponentId, TEXT("pressed"));
    }
}

void UTigerStudioButton::HandleReleased()
{
    if (TigerOwner)
    {
        TigerOwner->ExecuteTigerInteraction(TigerComponentId, TEXT("released"));
    }
}
