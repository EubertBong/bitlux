"""Repository layer: the only way application code reads or writes a table.

Start with ``tenant_transaction()`` from .context -- every repository fails
closed without it -- then instantiate repositories on the session.
"""

from .activities import ActivityRepository
from .aircraft import AircraftModelRepository, AircraftRepository, ManufacturerRepository
from .airports import AirportRepository, FBORepository, haversine_nm
from .audit import AuditEvent, AuditLogRepository
from .base import (
    MAX_PAGE_SIZE,
    BaseRepository,
    HardDeleteNotAllowed,
    ImmutableModel,
    NotFound,
    RepositoryError,
    SharedCatalogRepository,
)
from .bookings import BookingRepository
from .clients import ClientRepository
from .contacts import AccountHolderRepository, ContactChannelRepository, ContactRepository, SegmentRepository
from .context import (
    TenantContextMissing,
    current_actor_type,
    current_client_id,
    current_client_id_or_none,
    current_user_id,
    tenant_context,
    tenant_transaction,
)
from .crew import CrewMemberRepository
from .documents import DocumentLinkRepository, DocumentRepository
from .empty_legs import EmptyLegRepository
from .invoices import AGING_BUCKETS, UNSETTLED, AgingBucket, AgingReport, InvoiceRepository
from .operators import OperatorRepository, OperatorSafetyRatingRepository
from .passengers import PassengerRepository, TravelDocumentRepository
from .payments import PaymentRepository
from .polymorphic import ENTITY_MODEL_MAP, ENTITY_TABLE_MAP, EntityNotFound, ensure_entity_exists, entity_type_of, resolve_entity
from .quotes import QuoteLineItemRepository, QuoteRepository
from .tags import EntityTagRepository, TagRepository
from .tasks import TaskRepository
from .trips import LegRepository, TripRepository

__all__ = [n for n in dir() if not n.startswith("_")]
