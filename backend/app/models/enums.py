"""Python mirrors of every PostgreSQL ENUM type (migration 002 / DATA_MODEL.md 2).

Member *values* are the exact database labels; `pg_enum()` in .base binds a class to its
PostgreSQL type by `__pg_name__` and persists values (not member names). Enums are append-only
in the database; add members here in the same commit as the ALTER TYPE ... ADD VALUE.
"""

from enum import Enum


class ClientStatus(str, Enum):
    __pg_name__ = "client_status"

    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class UserRole(str, Enum):
    __pg_name__ = "user_role"

    OWNER = "owner"
    ADMIN = "admin"
    BROKER = "broker"
    OPS = "ops"
    FINANCE = "finance"
    READ_ONLY = "read_only"


class UserStatus(str, Enum):
    __pg_name__ = "user_status"

    INVITED = "invited"
    ACTIVE = "active"
    DISABLED = "disabled"
    LOCKED = "locked"


class SegmentType(str, Enum):
    __pg_name__ = "segment_type"

    UHNW = "uhnw"
    CORPORATE = "corporate"
    FAMILY_OFFICE = "family_office"
    GOVERNMENT = "government"
    SPORTS = "sports"
    ENTERTAINMENT = "entertainment"
    MEDICAL = "medical"
    GROUP_CHARTER = "group_charter"
    CARGO = "cargo"
    BROKER_PARTNER = "broker_partner"
    OTHER = "other"


class ContactType(str, Enum):
    __pg_name__ = "contact_type"

    INDIVIDUAL = "individual"
    COMPANY = "company"


class ContactStatus(str, Enum):
    __pg_name__ = "contact_status"

    LEAD = "lead"
    PROSPECT = "prospect"
    ACTIVE = "active"
    DORMANT = "dormant"
    CHURNED = "churned"
    BLOCKED = "blocked"


class LeadSource(str, Enum):
    __pg_name__ = "lead_source"

    REFERRAL = "referral"
    WEBSITE = "website"
    INBOUND_CALL = "inbound_call"
    OUTBOUND = "outbound"
    BROKER_NETWORK = "broker_network"
    EVENT = "event"
    ADVERTISING = "advertising"
    PARTNER = "partner"
    EMPTY_LEG_ALERT = "empty_leg_alert"
    IMPORT = "import"
    OTHER = "other"


class ChannelType(str, Enum):
    __pg_name__ = "channel_type"

    EMAIL = "email"
    PHONE = "phone"
    MOBILE = "mobile"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    SIGNAL = "signal"
    FAX = "fax"
    WEBSITE = "website"
    LINKEDIN = "linkedin"
    OTHER = "other"


class AddressType(str, Enum):
    __pg_name__ = "address_type"

    BILLING = "billing"
    HOME = "home"
    OFFICE = "office"
    SHIPPING = "shipping"
    OTHER = "other"


class PassengerStatus(str, Enum):
    __pg_name__ = "passenger_status"

    ACTIVE = "active"
    INACTIVE = "inactive"
    DECEASED = "deceased"


class PaxRelationship(str, Enum):
    __pg_name__ = "pax_relationship"

    SELF = "self"
    SPOUSE = "spouse"
    PARTNER = "partner"
    CHILD = "child"
    FAMILY = "family"
    EMPLOYEE = "employee"
    ASSISTANT = "assistant"
    COLLEAGUE = "colleague"
    GUEST = "guest"
    OTHER = "other"


class TravelDocumentType(str, Enum):
    __pg_name__ = "travel_document_type"

    PASSPORT = "passport"
    VISA = "visa"
    NATIONAL_ID = "national_id"
    DRIVERS_LICENSE = "drivers_license"
    RESIDENCE_PERMIT = "residence_permit"
    GLOBAL_ENTRY = "global_entry"
    KNOWN_TRAVELER = "known_traveler"
    CREW_LICENSE = "crew_license"
    CREW_MEDICAL = "crew_medical"
    OTHER = "other"


class AccountType(str, Enum):
    __pg_name__ = "account_type"

    INDIVIDUAL = "individual"
    CORPORATE = "corporate"
    FAMILY_OFFICE = "family_office"
    JET_CARD = "jet_card"
    FRACTIONAL = "fractional"
    GOVERNMENT = "government"
    BROKER_PARTNER = "broker_partner"


class AccountStatus(str, Enum):
    __pg_name__ = "account_status"

    PENDING = "pending"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class PaymentTerms(str, Enum):
    __pg_name__ = "payment_terms"

    PREPAID = "prepaid"
    DUE_ON_RECEIPT = "due_on_receipt"
    NET_7 = "net_7"
    NET_15 = "net_15"
    NET_30 = "net_30"
    NET_45 = "net_45"
    NET_60 = "net_60"
    ON_ACCOUNT = "on_account"


class PaymentMethod(str, Enum):
    __pg_name__ = "payment_method"

    WIRE = "wire"
    ACH = "ach"
    SEPA = "sepa"
    CREDIT_CARD = "credit_card"
    CHECK = "check"
    JET_CARD_DEBIT = "jet_card_debit"
    ESCROW = "escrow"
    CRYPTO = "crypto"
    OTHER = "other"


class PaymentStatus(str, Enum):
    __pg_name__ = "payment_status"

    PENDING = "pending"
    CLEARED = "cleared"
    FAILED = "failed"
    REFUNDED = "refunded"
    CHARGEBACK = "chargeback"


class InvoiceType(str, Enum):
    __pg_name__ = "invoice_type"

    DEPOSIT = "deposit"
    BALANCE = "balance"
    FULL = "full"
    CREDIT_NOTE = "credit_note"
    ADJUSTMENT = "adjustment"


class InvoiceStatus(str, Enum):
    __pg_name__ = "invoice_status"

    DRAFT = "draft"
    ISSUED = "issued"
    SENT = "sent"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    VOID = "void"
    REFUNDED = "refunded"
    WRITTEN_OFF = "written_off"


class LineItemType(str, Enum):
    __pg_name__ = "line_item_type"

    FLIGHT_HOURS = "flight_hours"
    POSITIONING = "positioning"
    FUEL_SURCHARGE = "fuel_surcharge"
    FEDERAL_EXCISE_TAX = "federal_excise_tax"
    SEGMENT_FEE = "segment_fee"
    INTERNATIONAL_FEE = "international_fee"
    LANDING_FEE = "landing_fee"
    RAMP_FEE = "ramp_fee"
    HANDLING = "handling"
    OVERFLIGHT = "overflight"
    CUSTOMS = "customs"
    CATERING = "catering"
    GROUND_TRANSPORT = "ground_transport"
    DEICING = "deicing"
    OVERNIGHT = "overnight"
    CREW_EXPENSE = "crew_expense"
    WIFI = "wifi"
    PET_FEE = "pet_fee"
    PEAK_DAY_SURCHARGE = "peak_day_surcharge"
    SHORT_NOTICE = "short_notice"
    DISCOUNT = "discount"
    COMMISSION = "commission"
    CREDIT_CARD_FEE = "credit_card_fee"
    OTHER = "other"


class AircraftCategory(str, Enum):
    __pg_name__ = "aircraft_category"

    PISTON = "piston"
    TURBOPROP = "turboprop"
    VERY_LIGHT_JET = "very_light_jet"
    LIGHT_JET = "light_jet"
    MIDSIZE_JET = "midsize_jet"
    SUPER_MIDSIZE_JET = "super_midsize_jet"
    HEAVY_JET = "heavy_jet"
    ULTRA_LONG_RANGE = "ultra_long_range"
    VIP_AIRLINER = "vip_airliner"
    HELICOPTER = "helicopter"


class AircraftStatus(str, Enum):
    __pg_name__ = "aircraft_status"

    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    AOG = "aog"
    STORED = "stored"
    FOR_SALE = "for_sale"
    SOLD = "sold"
    RETIRED = "retired"


class OperatorStatus(str, Enum):
    __pg_name__ = "operator_status"

    PROSPECT = "prospect"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    CONDITIONAL = "conditional"
    SUSPENDED = "suspended"
    BLACKLISTED = "blacklisted"


class RegulatoryPart(str, Enum):
    __pg_name__ = "regulatory_part"

    PART_91 = "part_91"
    PART_91K = "part_91k"
    PART_121 = "part_121"
    PART_135 = "part_135"
    EASA_CAT = "easa_cat"
    EASA_NCO = "easa_nco"
    EASA_SPO = "easa_spo"
    OTHER = "other"


class SafetyProgram(str, Enum):
    __pg_name__ = "safety_program"

    ARGUS = "argus"
    WYVERN = "wyvern"
    ISBAO = "isbao"
    ISBAH = "isbah"
    ACSF = "acsf"
    TSA_TWELVE_FIVE = "tsa_twelve_five"
    EASA_SMS = "easa_sms"
    OTHER = "other"


class SafetyRatingLevel(str, Enum):
    __pg_name__ = "safety_rating_level"

    NOT_RATED = "not_rated"
    ARGUS_GOLD = "argus_gold"
    ARGUS_GOLD_PLUS = "argus_gold_plus"
    ARGUS_PLATINUM = "argus_platinum"
    WYVERN_REGISTERED = "wyvern_registered"
    WYVERN_WINGMAN = "wyvern_wingman"
    WYVERN_WINGMAN_PLUS = "wyvern_wingman_plus"
    ISBAO_STAGE_1 = "isbao_stage_1"
    ISBAO_STAGE_2 = "isbao_stage_2"
    ISBAO_STAGE_3 = "isbao_stage_3"
    ACSF_REGISTERED = "acsf_registered"
    OTHER = "other"


class CrewRole(str, Enum):
    __pg_name__ = "crew_role"

    PIC = "pic"
    SIC = "sic"
    RELIEF_PILOT = "relief_pilot"
    FLIGHT_ENGINEER = "flight_engineer"
    FLIGHT_ATTENDANT = "flight_attendant"
    FLIGHT_NURSE = "flight_nurse"
    FLIGHT_PHYSICIAN = "flight_physician"
    GROUND_OPS = "ground_ops"
    OBSERVER = "observer"


class CrewStatus(str, Enum):
    __pg_name__ = "crew_status"

    ACTIVE = "active"
    INACTIVE = "inactive"
    TRAINING = "training"
    ON_LEAVE = "on_leave"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class TripType(str, Enum):
    __pg_name__ = "trip_type"

    CHARTER = "charter"
    OWNER_FLIGHT = "owner_flight"
    EMPTY_REPOSITION = "empty_reposition"
    DEMO = "demo"
    MAINTENANCE_FERRY = "maintenance_ferry"
    AIR_AMBULANCE = "air_ambulance"
    CARGO = "cargo"
    GROUP = "group"


class TripStatus(str, Enum):
    __pg_name__ = "trip_status"

    DRAFT = "draft"
    SOURCING = "sourcing"
    QUOTED = "quoted"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class LegStatus(str, Enum):
    __pg_name__ = "leg_status"

    SCHEDULED = "scheduled"
    RELEASED = "released"
    BOARDING = "boarding"
    DEPARTED = "departed"
    ENROUTE = "enroute"
    ARRIVED = "arrived"
    DELAYED = "delayed"
    DIVERTED = "diverted"
    CANCELLED = "cancelled"


class LegPurpose(str, Enum):
    __pg_name__ = "leg_purpose"

    REVENUE = "revenue"
    POSITIONING = "positioning"
    FERRY = "ferry"
    MAINTENANCE = "maintenance"
    TRAINING = "training"


class EmptyLegStatus(str, Enum):
    __pg_name__ = "empty_leg_status"

    DRAFT = "draft"
    AVAILABLE = "available"
    ON_HOLD = "on_hold"
    BOOKED = "booked"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class EmptyLegSource(str, Enum):
    __pg_name__ = "empty_leg_source"

    MANUAL = "manual"
    OPERATOR_FEED = "operator_feed"
    AVINODE = "avinode"
    EMAIL_PARSE = "email_parse"
    API_PARTNER = "api_partner"


class QuoteStatus(str, Enum):
    __pg_name__ = "quote_status"

    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    NEGOTIATING = "negotiating"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"
    SUPERSEDED = "superseded"


class BookingStatus(str, Enum):
    __pg_name__ = "booking_status"

    PENDING = "pending"
    CONFIRMED = "confirmed"
    CONTRACT_SENT = "contract_sent"
    CONTRACT_SIGNED = "contract_signed"
    FUNDS_PENDING = "funds_pending"
    FUNDS_RECEIVED = "funds_received"
    FLOWN = "flown"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"


class DocumentType(str, Enum):
    __pg_name__ = "document_type"

    CONTRACT = "contract"
    CHARTER_AGREEMENT = "charter_agreement"
    QUOTE_PDF = "quote_pdf"
    INVOICE_PDF = "invoice_pdf"
    RECEIPT = "receipt"
    PASSPORT_SCAN = "passport_scan"
    VISA_SCAN = "visa_scan"
    ID_SCAN = "id_scan"
    INSURANCE_CERTIFICATE = "insurance_certificate"
    AOC_CERTIFICATE = "aoc_certificate"
    OPS_SPECIFICATION = "ops_specification"
    SAFETY_AUDIT_REPORT = "safety_audit_report"
    W9 = "w9"
    TAX_FORM = "tax_form"
    CATERING_ORDER = "catering_order"
    HANDLING_CONFIRMATION = "handling_confirmation"
    FLIGHT_RELEASE = "flight_release"
    GENDEC = "gendec"
    WEIGHT_BALANCE = "weight_balance"
    APIS_MANIFEST = "apis_manifest"
    TRIP_SHEET = "trip_sheet"
    PHOTO = "photo"
    OTHER = "other"


class DocumentStatus(str, Enum):
    __pg_name__ = "document_status"

    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class StorageProvider(str, Enum):
    __pg_name__ = "storage_provider"

    S3 = "s3"
    GCS = "gcs"
    AZURE_BLOB = "azure_blob"
    LOCAL = "local"


class TaskStatus(str, Enum):
    __pg_name__ = "task_status"

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    __pg_name__ = "task_priority"

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskType(str, Enum):
    __pg_name__ = "task_type"

    CALL = "call"
    EMAIL = "email"
    FOLLOW_UP = "follow_up"
    DOCUMENT_REQUEST = "document_request"
    DOCUMENT_EXPIRY = "document_expiry"
    PAYMENT_CHASE = "payment_chase"
    QUOTE_PREP = "quote_prep"
    OPS_CHECK = "ops_check"
    COMPLIANCE_REVIEW = "compliance_review"
    OTHER = "other"


class ActivityType(str, Enum):
    __pg_name__ = "activity_type"

    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"
    NOTE = "note"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    SITE_VISIT = "site_visit"
    SYSTEM = "system"


class ActivityDirection(str, Enum):
    __pg_name__ = "activity_direction"

    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"


class AuditAction(str, Enum):
    __pg_name__ = "audit_action"

    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    SOFT_DELETE = "soft_delete"
    RESTORE = "restore"
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    EXPORT = "export"
    DOWNLOAD = "download"
    PERMISSION_CHANGE = "permission_change"
    IMPERSONATE_START = "impersonate_start"
    IMPERSONATE_END = "impersonate_end"


class ActorType(str, Enum):
    __pg_name__ = "actor_type"

    USER = "user"
    SYSTEM = "system"
    API_KEY = "api_key"
    INTEGRATION = "integration"
    IMPERSONATION = "impersonation"
    ANONYMOUS = "anonymous"


class EntityType(str, Enum):
    __pg_name__ = "entity_type"

    CLIENT = "client"
    USER = "user"
    SEGMENT = "segment"
    CONTACT = "contact"
    PASSENGER = "passenger"
    ACCOUNT_HOLDER = "account_holder"
    TRAVEL_DOCUMENT = "travel_document"
    MANUFACTURER = "manufacturer"
    AIRCRAFT_MODEL = "aircraft_model"
    AIRCRAFT = "aircraft"
    OPERATOR = "operator"
    OPERATOR_SAFETY_RATING = "operator_safety_rating"
    CREW_MEMBER = "crew_member"
    AIRPORT = "airport"
    FBO = "fbo"
    TRIP = "trip"
    LEG = "leg"
    LEG_PASSENGER = "leg_passenger"
    LEG_CREW = "leg_crew"
    EMPTY_LEG = "empty_leg"
    QUOTE = "quote"
    BOOKING = "booking"
    INVOICE = "invoice"
    PAYMENT = "payment"
    DOCUMENT = "document"
    TASK = "task"
    ACTIVITY = "activity"


__all__ = ["ClientStatus", "UserRole", "UserStatus", "SegmentType", "ContactType", "ContactStatus", "LeadSource", "ChannelType", "AddressType", "PassengerStatus", "PaxRelationship", "TravelDocumentType", "AccountType", "AccountStatus", "PaymentTerms", "PaymentMethod", "PaymentStatus", "InvoiceType", "InvoiceStatus", "LineItemType", "AircraftCategory", "AircraftStatus", "OperatorStatus", "RegulatoryPart", "SafetyProgram", "SafetyRatingLevel", "CrewRole", "CrewStatus", "TripType", "TripStatus", "LegStatus", "LegPurpose", "EmptyLegStatus", "EmptyLegSource", "QuoteStatus", "BookingStatus", "DocumentType", "DocumentStatus", "StorageProvider", "TaskStatus", "TaskPriority", "TaskType", "ActivityType", "ActivityDirection", "AuditAction", "ActorType", "EntityType"]
