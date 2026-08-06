#include "TigerStudioRoundedCardHost.h"

#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Widgets/Layout/SConstraintCanvas.h"

namespace
{
class STigerStudioRoundedCardCanvas : public SConstraintCanvas
{
public:
    SLATE_BEGIN_ARGS(STigerStudioRoundedCardCanvas) {}
        SLATE_ARGUMENT(TWeakObjectPtr<UTigerStudioRoundedCardHost>, Owner)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs)
    {
        Owner = InArgs._Owner;
        SConstraintCanvas::Construct(SConstraintCanvas::FArguments());
    }

    virtual int32 OnPaint(
        const FPaintArgs& Args,
        const FGeometry& AllottedGeometry,
        const FSlateRect& MyCullingRect,
        FSlateWindowElementList& OutDrawElements,
        const int32 LayerId,
        const FWidgetStyle& InWidgetStyle,
        const bool bParentEnabled) const override
    {
        if (UTigerStudioRoundedCardHost* Host = Owner.Get())
        {
            // Slate local units are already the UMG material's coordinate
            // units. Deliberately do not multiply by application DPI scale.
            Host->UpdateTigerMaterialSizeForGeometry(
                AllottedGeometry.GetLocalSize());
        }
        return SConstraintCanvas::OnPaint(
            Args,
            AllottedGeometry,
            MyCullingRect,
            OutDrawElements,
            LayerId,
            InWidgetStyle,
            bParentEnabled);
    }

protected:
    virtual FVector2D ComputeDesiredSize(float LayoutScaleMultiplier) const override
    {
        if (const UTigerStudioRoundedCardHost* Host = Owner.Get())
        {
            // VisualPadding belongs to paint bounds, not layout bounds.
            return Host->TigerFixedCardSize;
        }
        return SConstraintCanvas::ComputeDesiredSize(LayoutScaleMultiplier);
    }

private:
    TWeakObjectPtr<UTigerStudioRoundedCardHost> Owner;
};
}

TSharedRef<SWidget> UTigerStudioRoundedCardHost::RebuildWidget()
{
    MyCanvas = SNew(STigerStudioRoundedCardCanvas)
        .Owner(this);

    for (UPanelSlot* PanelSlot : Slots)
    {
        if (UCanvasPanelSlot* TypedSlot = Cast<UCanvasPanelSlot>(PanelSlot))
        {
            TypedSlot->Parent = this;
            TypedSlot->BuildSlot(MyCanvas.ToSharedRef());
        }
    }
    return MyCanvas.ToSharedRef();
}

void UTigerStudioRoundedCardHost::UpdateTigerMaterialSize()
{
    if (!TigerSizeBinding.Equals(
            TEXT("WidgetGeometry"),
            ESearchCase::CaseSensitive))
    {
        return;
    }

    UpdateTigerMaterialSizeForGeometry(GetCachedGeometry().GetLocalSize());
}

void UTigerStudioRoundedCardHost::UpdateTigerMaterialSizeForGeometry(
    const FVector2D& CardSize)
{
    if (!TigerSizeBinding.Equals(
            TEXT("WidgetGeometry"),
            ESearchCase::CaseSensitive))
    {
        return;
    }

    UImage* Visual = GetChildrenCount() > 0
        ? Cast<UImage>(GetChildAt(0))
        : nullptr;
    UCanvasPanelSlot* VisualSlot = Visual
        ? Cast<UCanvasPanelSlot>(Visual->Slot)
        : nullptr;
    if (!Visual || !VisualSlot)
    {
        return;
    }

    if (!FMath::IsFinite(CardSize.X)
        || !FMath::IsFinite(CardSize.Y)
        || CardSize.X <= UE_SMALL_NUMBER
        || CardSize.Y <= UE_SMALL_NUMBER)
    {
        // A zero allocation can occur while an anchored parent collapses.
        // Clear the non-clipping padded surface so the previous larger frame
        // cannot remain visible outside the now-empty host.
        Visual->SetDesiredSizeOverride(FVector2D::ZeroVector);
        VisualSlot->SetPosition(FVector2D::ZeroVector);
        VisualSlot->SetSize(FVector2D::ZeroVector);
        VisualSlot->SetAutoSize(false);
        TigerLastAppliedCardSize = FVector2D::ZeroVector;
        return;
    }

    const bool bSizeChanged = !CardSize.Equals(
        TigerLastAppliedCardSize,
        0.01);
    if (bSizeChanged)
    {
        const FVector2D SurfaceSize(
            CardSize.X + TigerVisualPadding.Left + TigerVisualPadding.Right,
            CardSize.Y + TigerVisualPadding.Top + TigerVisualPadding.Bottom);
        Visual->SetDesiredSizeOverride(SurfaceSize);
        VisualSlot->SetPosition(FVector2D(
            -TigerVisualPadding.Left,
            -TigerVisualPadding.Top));
        VisualSlot->SetSize(SurfaceSize);
        VisualSlot->SetAutoSize(false);
        TigerLastAppliedCardSize = CardSize;
    }

    const bool bNeedsMaterialInstance = !TigerMaterialInstance;
    if (bNeedsMaterialInstance)
    {
        TigerMaterialInstance = Visual->GetDynamicMaterial();
    }
    if (TigerMaterialInstance && (bSizeChanged || bNeedsMaterialInstance))
    {
        TigerMaterialInstance->SetVectorParameterValue(
            TEXT("CardSize"),
            FLinearColor(CardSize.X, CardSize.Y, 0.0, 0.0));
    }
}

bool UTigerStudioRoundedCardHost::TryGetTigerMaterialCardSize(
    FVector2D& OutSize)
{
    if (!TigerMaterialInstance)
    {
        return false;
    }
    const FLinearColor Value =
        TigerMaterialInstance->K2_GetVectorParameterValue(TEXT("CardSize"));
    OutSize = FVector2D(Value.R, Value.G);
    return FMath::IsFinite(OutSize.X) && FMath::IsFinite(OutSize.Y);
}
