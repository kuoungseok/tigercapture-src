"""NLE/project-bin adapter methods for Python Actions."""
from __future__ import annotations

from app.actions.editor_adapter_nle_auditions import NleAuditionAdapterMixin
from app.actions.editor_adapter_nle_multicam import NleMulticamAdapterMixin
from app.actions.editor_adapter_nle_project_bin import NleProjectBinAdapterMixin
from app.actions.editor_adapter_nle_readiness import NleReadinessAdapterMixin
from app.actions.editor_adapter_nle_source_record import NleSourceRecordAdapterMixin
from app.actions.editor_adapter_nle_storyline import NleStorylineAdapterMixin
from app.actions.editor_adapter_nle_visual import NleVisualFeedbackAdapterMixin


class NleAdapterMixin(
    NleReadinessAdapterMixin,
    NleStorylineAdapterMixin,
    NleAuditionAdapterMixin,
    NleMulticamAdapterMixin,
    NleSourceRecordAdapterMixin,
    NleProjectBinAdapterMixin,
    NleVisualFeedbackAdapterMixin,
):
    """Facade for NLE Source/Record, project-bin, readiness, and multicam methods."""
    pass
