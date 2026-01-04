"""
Query Optimization Module

This module provides optimized query patterns and utilities specifically designed
for the UltimateCo planner backend to reduce database latency and improve performance.
"""

from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session, selectinload, joinedload, contains_eager
from sqlalchemy import select, func, and_, or_, text, case
from sqlalchemy.sql import Select
from app.models.vendor_models import Vendor, VendorBooking, VendorPayment, VendorReview
from app.models.user_models import User
from app.models.event_models import Event
from app.core.database_performance import query_performance_tracker, query_timer
import logging

logger = logging.getLogger(__name__)

class VendorQueryOptimizer:
    """Optimized queries for vendor-related operations"""
    
    @staticmethod
    @query_performance_tracker
    def get_vendors_with_stats(
        db: Session,
        city: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Vendor]:
        """
        Optimized query to get vendors with their statistics in a single query.
        Uses joins and subqueries to avoid N+1 problems.
        """
        with query_timer("get_vendors_with_stats"):
            # Build base query with eager loading
            query = (
                db.query(Vendor)
                .options(
                    selectinload(Vendor.services),
                    selectinload(Vendor.portfolio_items)
                )
            )
            
            # Apply filters
            if city:
                query = query.filter(Vendor.city.ilike(f"%{city}%"))
            if category:
                query = query.filter(Vendor.category == category)
            
            # Filter active vendors only
            query = query.filter(
                and_(
                    Vendor.status.in_(['active', 'verified']),
                    Vendor.is_deleted == False
                )
            )
            
            # Order by rating and featured status
            query = query.order_by(
                Vendor.is_featured.desc(),
                Vendor.average_rating.desc(),
                Vendor.total_reviews.desc()
            )
            
            return query.offset(offset).limit(limit).all()
    
    @staticmethod
    @query_performance_tracker
    def get_vendor_bookings_with_payments(
        db: Session,
        vendor_id: int,
        status_filter: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[VendorBooking]:
        """
        Optimized query to get vendor bookings with all related payment data.
        Prevents N+1 queries by eager loading payments and related entities.
        """
        with query_timer("get_vendor_bookings_with_payments"):
            query = (
                db.query(VendorBooking)
                .options(
                    joinedload(VendorBooking.payments),
                    joinedload(VendorBooking.event),
                    joinedload(VendorBooking.booked_by),
                    joinedload(VendorBooking.service)
                )
                .filter(VendorBooking.vendor_id == vendor_id)
            )
            
            if status_filter:
                query = query.filter(VendorBooking.status.in_(status_filter))
            
            return (
                query
                .order_by(VendorBooking.service_date.desc())
                .limit(limit)
                .all()
            )
    
    @staticmethod
    @query_performance_tracker
    def get_payment_analytics(
        db: Session,
        vendor_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Optimized analytics query for payment data using aggregations.
        Returns summary statistics without loading individual records.
        """
        with query_timer("get_payment_analytics"):
            # Base query for payment aggregations
            base_query = db.query(VendorPayment)
            
            if vendor_id:
                base_query = base_query.join(VendorBooking).filter(
                    VendorBooking.vendor_id == vendor_id
                )
            
            if start_date:
                base_query = base_query.filter(VendorPayment.paid_at >= start_date)
            if end_date:
                base_query = base_query.filter(VendorPayment.paid_at <= end_date)
            
            # Aggregate queries
            total_revenue = (
                base_query
                .filter(VendorPayment.status == 'paid')
                .with_entities(func.sum(VendorPayment.amount))
                .scalar() or 0
            )
            
            payment_count = (
                base_query
                .filter(VendorPayment.status == 'paid')
                .count()
            )
            
            avg_payment = (
                base_query
                .filter(VendorPayment.status == 'paid')
                .with_entities(func.avg(VendorPayment.amount))
                .scalar() or 0
            )
            
            # Status breakdown
            status_breakdown = (
                base_query
                .with_entities(
                    VendorPayment.status,
                    func.count(VendorPayment.id).label('count'),
                    func.sum(VendorPayment.amount).label('total_amount')
                )
                .group_by(VendorPayment.status)
                .all()
            )
            
            return {
                'total_revenue': float(total_revenue),
                'payment_count': payment_count,
                'average_payment': float(avg_payment),
                'status_breakdown': [
                    {
                        'status': status,
                        'count': count,
                        'total_amount': float(total_amount or 0)
                    }
                    for status, count, total_amount in status_breakdown
                ]
            }

class UserQueryOptimizer:
    """Optimized queries for user-related operations"""
    
    @staticmethod
    @query_performance_tracker
    def get_user_dashboard_data(db: Session, user_id: int) -> Dict[str, Any]:
        """
        Optimized query to get all user dashboard data in minimal queries.
        Combines multiple related queries to reduce database round trips.
        """
        with query_timer("get_user_dashboard_data"):
            # Get user with basic relationships
            user = (
                db.query(User)
                .options(
                    selectinload(User.events),
                    selectinload(User.vendor_bookings).selectinload(VendorBooking.vendor),
                    selectinload(User.vendor_payments)
                )
                .filter(User.id == user_id)
                .first()
            )
            
            if not user:
                return {}
            
            # Get upcoming events count
            upcoming_events = (
                db.query(func.count(Event.id))
                .filter(
                    and_(
                        Event.creator_id == user_id,
                        Event.start_datetime > func.now(),
                        Event.is_deleted == False
                    )
                )
                .scalar()
            )
            
            # Get pending bookings count
            pending_bookings = (
                db.query(func.count(VendorBooking.id))
                .filter(
                    and_(
                        VendorBooking.booked_by_id == user_id,
                        VendorBooking.status == 'pending'
                    )
                )
                .scalar()
            )
            
            return {
                'user': user,
                'upcoming_events_count': upcoming_events,
                'pending_bookings_count': pending_bookings,
                'total_events': len(user.events),
                'total_bookings': len(user.vendor_bookings)
            }

class EventQueryOptimizer:
    """Optimized queries for event-related operations"""
    
    @staticmethod
    @query_performance_tracker
    def get_events_with_vendors(
        db: Session,
        user_id: Optional[int] = None,
        city: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Event]:
        """
        Optimized query to get events with their vendor bookings.
        Uses selective eager loading to prevent N+1 queries.
        """
        with query_timer("get_events_with_vendors"):
            query = (
                db.query(Event)
                .options(
                    selectinload(Event.vendor_bookings)
                    .selectinload(VendorBooking.vendor),
                    selectinload(Event.vendor_bookings)
                    .selectinload(VendorBooking.payments)
                )
            )
            
            # Apply filters
            if user_id:
                query = query.filter(Event.creator_id == user_id)
            if city:
                query = query.filter(Event.venue_city.ilike(f"%{city}%"))
            
            # Filter active events
            query = query.filter(Event.is_deleted == False)
            
            return (
                query
                .order_by(Event.start_datetime.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )

class SearchQueryOptimizer:
    """Optimized search queries with full-text search capabilities"""
    
    @staticmethod
    @query_performance_tracker
    def search_vendors_optimized(
        db: Session,
        search_term: str,
        city: Optional[str] = None,
        category: Optional[str] = None,
        min_rating: Optional[float] = None,
        limit: int = 20
    ) -> List[Vendor]:
        """
        Optimized vendor search using database-level text search.
        Uses indexes and ranking for better performance.
        """
        with query_timer("search_vendors_optimized"):
            # Use PostgreSQL full-text search if available
            search_vector = func.to_tsvector('english', 
                func.coalesce(Vendor.business_name, '') + ' ' +
                func.coalesce(Vendor.display_name, '') + ' ' +
                func.coalesce(Vendor.description, '')
            )
            
            search_query = func.plainto_tsquery('english', search_term)
            
            query = (
                db.query(Vendor)
                .filter(
                    and_(
                        search_vector.op('@@')(search_query),
                        Vendor.status.in_(['active', 'verified']),
                        Vendor.is_deleted == False
                    )
                )
            )
            
            # Apply additional filters
            if city:
                query = query.filter(Vendor.city.ilike(f"%{city}%"))
            if category:
                query = query.filter(Vendor.category == category)
            if min_rating:
                query = query.filter(Vendor.average_rating >= min_rating)
            
            # Order by relevance and rating
            query = query.order_by(
                func.ts_rank(search_vector, search_query).desc(),
                Vendor.average_rating.desc()
            )
            
            return query.limit(limit).all()

class PaginationOptimizer:
    """Optimized pagination utilities"""
    
    @staticmethod
    def get_paginated_results(
        query: Select,
        page: int = 1,
        per_page: int = 20,
        max_per_page: int = 100
    ) -> Dict[str, Any]:
        """
        Optimized pagination that uses efficient counting and limits.
        """
        # Ensure reasonable limits
        per_page = min(per_page, max_per_page)
        offset = (page - 1) * per_page
        
        # Get total count efficiently
        count_query = select(func.count()).select_from(query.subquery())
        total = query.session.execute(count_query).scalar()
        
        # Get paginated results
        items = query.offset(offset).limit(per_page).all()
        
        return {
            'items': items,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
            'has_prev': page > 1,
            'has_next': page * per_page < total
        }

class BulkOperationOptimizer:
    """Optimized bulk operations to reduce database load"""
    
    @staticmethod
    @query_performance_tracker
    def bulk_update_vendor_stats(db: Session, vendor_ids: List[int]) -> None:
        """
        Bulk update vendor statistics using efficient SQL operations.
        """
        with query_timer("bulk_update_vendor_stats"):
            # Update average ratings
            rating_update = text("""
                UPDATE vendors 
                SET average_rating = subquery.avg_rating,
                    total_reviews = subquery.review_count
                FROM (
                    SELECT 
                        vendor_id,
                        AVG(rating) as avg_rating,
                        COUNT(*) as review_count
                    FROM vendor_reviews 
                    WHERE vendor_id = ANY(:vendor_ids) 
                    AND is_approved = true
                    GROUP BY vendor_id
                ) AS subquery
                WHERE vendors.id = subquery.vendor_id
            """)
            
            db.execute(rating_update, {'vendor_ids': vendor_ids})
            
            # Update booking counts
            booking_update = text("""
                UPDATE vendors 
                SET total_bookings = subquery.booking_count
                FROM (
                    SELECT 
                        vendor_id,
                        COUNT(*) as booking_count
                    FROM vendor_bookings 
                    WHERE vendor_id = ANY(:vendor_ids)
                    AND status IN ('confirmed', 'completed')
                    GROUP BY vendor_id
                ) AS subquery
                WHERE vendors.id = subquery.vendor_id
            """)
            
            db.execute(booking_update, {'vendor_ids': vendor_ids})
            db.commit()
    
    @staticmethod
    @query_performance_tracker
    def cleanup_expired_idempotency_keys(db: Session, batch_size: int = 1000) -> int:
        """
        Efficiently clean up expired idempotency keys in batches.
        """
        with query_timer("cleanup_expired_idempotency_keys"):
            deleted_count = 0
            
            while True:
                # Delete in batches to avoid long-running transactions
                result = db.execute(text("""
                    DELETE FROM idempotency_keys 
                    WHERE id IN (
                        SELECT id FROM idempotency_keys 
                        WHERE expires_at < NOW() 
                        LIMIT :batch_size
                    )
                """), {'batch_size': batch_size})
                
                batch_deleted = result.rowcount
                deleted_count += batch_deleted
                
                if batch_deleted == 0:
                    break
                
                db.commit()
            
            return deleted_count

# Query optimization utilities
def add_query_hints(query: Select, hints: List[str]) -> Select:
    """Add database-specific query hints for optimization"""
    # This would be database-specific implementation
    # For PostgreSQL, we might use query comments or specific syntax
    return query

def optimize_join_order(query: Select) -> Select:
    """Optimize join order for better performance"""
    # This would analyze the query and reorder joins
    # Based on table sizes and selectivity
    return query