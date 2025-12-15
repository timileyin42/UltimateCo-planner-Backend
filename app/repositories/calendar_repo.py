"""
Calendar connection repository for database operations.
Provides CRUD operations for calendar connections and related data.
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, and_, or_
from datetime import datetime, timedelta

from app.models.calendar_models import CalendarConnection, CalendarEvent, CalendarSyncLog
from app.models.calendar_models import CalendarProviderEnum, SyncStatusEnum
from app.schemas.pagination import PaginationParams


class CalendarConnectionRepository:
    """Repository for calendar connection data access operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # Calendar Connection CRUD operations
    def get_by_id(
        self, 
        connection_id: int, 
        include_relations: bool = False
    ) -> Optional[CalendarConnection]:
        """Get calendar connection by ID with optional relation loading"""
        query = self.db.query(CalendarConnection).filter(CalendarConnection.id == connection_id)
        
        if include_relations:
            query = query.options(
                joinedload(CalendarConnection.user),
                joinedload(CalendarConnection.calendar_events),
                joinedload(CalendarConnection.sync_logs)
            )
        
        return query.first()
    
    def get_by_id_and_user(
        self, 
        connection_id: int, 
        user_id: int,
        include_relations: bool = False
    ) -> Optional[CalendarConnection]:
        """Get calendar connection by ID and user ID"""
        query = self.db.query(CalendarConnection).filter(
            CalendarConnection.id == connection_id,
            CalendarConnection.user_id == user_id
        )
        
        if include_relations:
            query = query.options(
                joinedload(CalendarConnection.user),
                joinedload(CalendarConnection.calendar_events),
                joinedload(CalendarConnection.sync_logs)
            )
        
        return query.first()
    
    def get_by_user_id(
        self,
        user_id: int,
        provider: Optional[str] = None,
        active_only: bool = False,
        include_relations: bool = False
    ) -> List[CalendarConnection]:
        """Get calendar connections by user ID with optional filters"""
        query = self.db.query(CalendarConnection).filter(CalendarConnection.user_id == user_id)
        
        if provider:
            provider_enum = CalendarProviderEnum(provider.upper())
            query = query.filter(CalendarConnection.provider == provider_enum)
        
        if active_only:
            query = query.filter(
                CalendarConnection.sync_enabled == True,
                CalendarConnection.sync_status != SyncStatusEnum.DISABLED
            )
        
        if include_relations:
            query = query.options(
                joinedload(CalendarConnection.user),
                joinedload(CalendarConnection.calendar_events),
                joinedload(CalendarConnection.sync_logs)
            )
        
        return query.order_by(desc(CalendarConnection.created_at)).all()
    
    def get_by_provider_and_calendar_id(
        self,
        user_id: int,
        provider: CalendarProviderEnum,
        calendar_id: str
    ) -> Optional[CalendarConnection]:
        """Get connection by provider and external calendar ID"""
        return self.db.query(CalendarConnection).filter(
            CalendarConnection.user_id == user_id,
            CalendarConnection.provider == provider,
            CalendarConnection.calendar_id == calendar_id
        ).first()
    
    def create(self, connection_data: Dict[str, Any]) -> CalendarConnection:
        """Create a new calendar connection"""
        connection = CalendarConnection(**connection_data)
        self.db.add(connection)
        self.db.commit()
        self.db.refresh(connection)
        return connection
    
    def update(self, connection: CalendarConnection) -> CalendarConnection:
        """Update calendar connection"""
        connection.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(connection)
        return connection
    
    def delete(self, connection_id: int) -> bool:
        """Delete calendar connection"""
        connection = self.get_by_id(connection_id)
        if connection:
            self.db.delete(connection)
            self.db.commit()
            return True
        return False
    
    def get_connections_for_sync(
        self,
        sync_frequency_minutes: int = 15
    ) -> List[CalendarConnection]:
        """Get connections that need syncing"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=sync_frequency_minutes)
        
        return self.db.query(CalendarConnection).filter(
            CalendarConnection.sync_enabled == True,
            CalendarConnection.auto_sync_enabled == True,
            CalendarConnection.sync_status.in_([SyncStatusEnum.SYNCED, SyncStatusEnum.PENDING]),
            or_(
                CalendarConnection.last_sync_at.is_(None),
                CalendarConnection.last_sync_at <= cutoff_time
            )
        ).all()
    
    def update_sync_status(
        self,
        connection_id: int,
        sync_status: SyncStatusEnum,
        error_message: Optional[str] = None
    ) -> bool:
        """Update connection sync status"""
        connection = self.get_by_id(connection_id)
        if connection:
            connection.sync_status = sync_status
            connection.last_sync_at = datetime.utcnow()
            
            if error_message:
                connection.sync_error_message = error_message
                connection.sync_error_count += 1
            else:
                connection.sync_error_message = None
                connection.sync_error_count = 0
            
            connection.updated_at = datetime.utcnow()
            self.db.commit()
            return True
        return False


class CalendarEventRepository:
    """Repository for calendar event data access operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(
        self, 
        event_id: int, 
        include_relations: bool = False
    ) -> Optional[CalendarEvent]:
        """Get calendar event by ID"""
        query = self.db.query(CalendarEvent).filter(CalendarEvent.id == event_id)
        
        if include_relations:
            query = query.options(
                joinedload(CalendarEvent.user),
                joinedload(CalendarEvent.calendar_connection),
                joinedload(CalendarEvent.attendees)
            )
        
        return query.first()
    
    def get_by_external_id(
        self,
        connection_id: int,
        external_event_id: str
    ) -> Optional[CalendarEvent]:
        """Get calendar event by external ID"""
        return self.db.query(CalendarEvent).filter(
            CalendarEvent.calendar_connection_id == connection_id,
            CalendarEvent.external_event_id == external_event_id
        ).first()
    
    def get_by_user_id(
        self,
        user_id: int,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[CalendarEvent], int]:
        """Get calendar events by user ID with pagination and filters"""
        query = self.db.query(CalendarEvent).filter(CalendarEvent.user_id == user_id)
        joined_connection = False
        
        if filters:
            if filters.get('connection_id'):
                query = query.filter(CalendarEvent.calendar_connection_id == filters['connection_id'])
            
            if filters.get('start_date'):
                query = query.filter(CalendarEvent.start_time >= filters['start_date'])
            
            if filters.get('end_date'):
                query = query.filter(CalendarEvent.start_time <= filters['end_date'])
            
            if filters.get('sync_status'):
                sync_status = SyncStatusEnum(filters['sync_status'])
                query = query.filter(CalendarEvent.sync_status == sync_status)

            if filters.get('provider'):
                if not joined_connection:
                    query = query.join(
                        CalendarConnection,
                        CalendarEvent.calendar_connection_id == CalendarConnection.id
                    )
                    joined_connection = True
                provider_enum = CalendarProviderEnum(filters['provider'].upper())
                query = query.filter(CalendarConnection.provider == provider_enum)
        
        total = query.count()
        
        events = query.order_by(desc(CalendarEvent.start_time)).offset(
            pagination.offset
        ).limit(pagination.limit).all()
        
        return events, total

    def count_by_user_id(self, user_id: int) -> int:
        """Count total calendar events for a user"""
        return self.db.query(CalendarEvent).filter(CalendarEvent.user_id == user_id).count()
    
    def create(self, event_data: Dict[str, Any]) -> CalendarEvent:
        """Create a new calendar event"""
        event = CalendarEvent(**event_data)
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
    
    def update(self, event: CalendarEvent) -> CalendarEvent:
        """Update calendar event"""
        event.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(event)
        return event
    
    def delete(self, event_id: int) -> bool:
        """Delete calendar event"""
        event = self.get_by_id(event_id)
        if event:
            self.db.delete(event)
            self.db.commit()
            return True
        return False


class CalendarSyncLogRepository:
    """Repository for calendar sync log data access operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_sync_log(
        self,
        connection_id: int,
        sync_type: str,
        sync_status: SyncStatusEnum,
        events_processed: int = 0,
        events_created: int = 0,
        events_updated: int = 0,
        events_deleted: int = 0,
        error_message: Optional[str] = None
    ) -> CalendarSyncLog:
        """Create a new sync log entry"""
        sync_log = CalendarSyncLog(
            calendar_connection_id=connection_id,
            sync_type=sync_type,
            sync_status=sync_status,
            events_processed=events_processed,
            events_created=events_created,
            events_updated=events_updated,
            events_deleted=events_deleted,
            error_message=error_message,
            sync_started_at=datetime.utcnow(),
            sync_completed_at=datetime.utcnow() if sync_status in [SyncStatusEnum.SYNCED, SyncStatusEnum.FAILED] else None
        )
        
        self.db.add(sync_log)
        self.db.commit()
        self.db.refresh(sync_log)
        return sync_log
    
    def get_recent_logs(
        self,
        connection_id: int,
        limit: int = 10
    ) -> List[CalendarSyncLog]:
        """Get recent sync logs for a connection"""
        return self.db.query(CalendarSyncLog).filter(
            CalendarSyncLog.calendar_connection_id == connection_id
        ).order_by(desc(CalendarSyncLog.sync_started_at)).limit(limit).all()
    
    def get_sync_stats(
        self,
        connection_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get sync statistics for a connection"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        logs = self.db.query(CalendarSyncLog).filter(
            CalendarSyncLog.calendar_connection_id == connection_id,
            CalendarSyncLog.sync_started_at >= cutoff_date
        ).all()
        
        total_syncs = len(logs)
        successful_syncs = len([log for log in logs if log.sync_status == SyncStatusEnum.SYNCED])
        failed_syncs = len([log for log in logs if log.sync_status == SyncStatusEnum.FAILED])
        
        total_events_processed = sum(log.events_processed or 0 for log in logs)
        total_events_created = sum(log.events_created or 0 for log in logs)
        total_events_updated = sum(log.events_updated or 0 for log in logs)
        total_events_deleted = sum(log.events_deleted or 0 for log in logs)
        
        return {
            'total_syncs': total_syncs,
            'successful_syncs': successful_syncs,
            'failed_syncs': failed_syncs,
            'success_rate': (successful_syncs / total_syncs * 100) if total_syncs > 0 else 0,
            'total_events_processed': total_events_processed,
            'total_events_created': total_events_created,
            'total_events_updated': total_events_updated,
            'total_events_deleted': total_events_deleted,
            'last_sync': logs[0].sync_started_at if logs else None
        }

    def count_errors_since(self, since: datetime, user_id: Optional[int] = None) -> int:
        """Count sync errors since a given timestamp (optionally scoped to user)"""
        query = self.db.query(CalendarSyncLog).join(
            CalendarConnection,
            CalendarSyncLog.calendar_connection_id == CalendarConnection.id
        ).filter(
            CalendarSyncLog.sync_status == SyncStatusEnum.FAILED,
            CalendarSyncLog.sync_started_at >= since
        )

        if user_id is not None:
            query = query.filter(CalendarConnection.user_id == user_id)

        return query.count()