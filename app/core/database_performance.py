"""
Database Performance Optimization Module

This module provides utilities for monitoring and optimizing database performance,
including query analysis, connection pool monitoring, and performance metrics.
"""

import time
from functools import wraps
from typing import Dict, List, Any, Optional, Callable
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, Query
from sqlalchemy.pool import Pool
from contextlib import contextmanager
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from app.core.logger import get_perf_logger

# Performance monitoring logger
perf_logger = get_perf_logger()

class QueryPerformanceMonitor:
    """Monitor and log slow database queries"""
    
    def __init__(self, slow_query_threshold: float = 1.0):
        self.slow_query_threshold = slow_query_threshold
        self.query_stats = defaultdict(list)
        self.slow_queries = deque(maxlen=100)  # Keep last 100 slow queries
        self._lock = threading.Lock()
    
    def log_query(self, query: str, duration: float, params: Dict = None):
        """Log query performance metrics"""
        with self._lock:
            self.query_stats[query].append({
                'duration': duration,
                'timestamp': datetime.utcnow(),
                'params': params
            })
            
            if duration > self.slow_query_threshold:
                self.slow_queries.append({
                    'query': query,
                    'duration': duration,
                    'timestamp': datetime.utcnow(),
                    'params': params
                })
                
                perf_logger.warning(
                    f"Slow query detected: {duration:.3f}s - {query[:200]}..."
                )
    
    def get_slow_queries(self, limit: int = 10) -> List[Dict]:
        """Get recent slow queries"""
        with self._lock:
            return list(self.slow_queries)[-limit:]
    
    def get_query_stats(self, query_pattern: str = None) -> Dict:
        """Get aggregated query statistics"""
        with self._lock:
            if query_pattern:
                matching_queries = {
                    k: v for k, v in self.query_stats.items() 
                    if query_pattern.lower() in k.lower()
                }
            else:
                matching_queries = dict(self.query_stats)
            
            stats = {}
            for query, executions in matching_queries.items():
                durations = [e['duration'] for e in executions]
                stats[query] = {
                    'count': len(durations),
                    'avg_duration': sum(durations) / len(durations),
                    'max_duration': max(durations),
                    'min_duration': min(durations),
                    'total_duration': sum(durations)
                }
            
            return stats

# Global query monitor instance
query_monitor = QueryPerformanceMonitor()

class ConnectionPoolMonitor:
    """Monitor database connection pool health"""
    
    def __init__(self):
        self.pool_stats = {
            'checked_out': 0,
            'checked_in': 0,
            'pool_size': 0,
            'checked_out_connections': 0,
            'overflow_connections': 0,
            'invalid_connections': 0
        }
        self._lock = threading.Lock()
    
    def update_stats(self, pool: Pool):
        """Update pool statistics"""
        with self._lock:
            self.pool_stats.update({
                'pool_size': pool.size(),
                'checked_out_connections': pool.checkedout(),
                'overflow_connections': pool.overflow(),
                'invalid_connections': pool.invalidated()
            })
    
    def get_stats(self) -> Dict:
        """Get current pool statistics"""
        with self._lock:
            return self.pool_stats.copy()
    
    def is_pool_healthy(self, warning_threshold: float = 0.8) -> bool:
        """Check if connection pool is healthy"""
        with self._lock:
            if self.pool_stats['pool_size'] == 0:
                return True
            
            utilization = (
                self.pool_stats['checked_out_connections'] / 
                self.pool_stats['pool_size']
            )
            
            return utilization < warning_threshold

# Global pool monitor instance
pool_monitor = ConnectionPoolMonitor()

def query_performance_tracker(func: Callable) -> Callable:
    """Decorator to track query performance in service methods"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Log performance if it's a database operation
            if duration > 0.1:  # Log queries taking more than 100ms
                perf_logger.info(
                    f"Service method {func.__name__} took {duration:.3f}s"
                )
            
            return result
        except Exception as e:
            duration = time.time() - start_time
            perf_logger.error(
                f"Service method {func.__name__} failed after {duration:.3f}s: {str(e)}"
            )
            raise
    return wrapper

@contextmanager
def query_timer(operation_name: str):
    """Context manager for timing database operations"""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        if duration > 0.5:  # Log operations taking more than 500ms
            perf_logger.warning(
                f"Long-running operation '{operation_name}' took {duration:.3f}s"
            )

class DatabaseOptimizer:
    """Database optimization utilities"""
    
    @staticmethod
    def analyze_query_plan(db: Session, query: str) -> Dict:
        """Analyze query execution plan (PostgreSQL specific)"""
        try:
            explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
            result = db.execute(text(explain_query)).fetchone()
            return result[0] if result else {}
        except Exception as e:
            perf_logger.error(f"Failed to analyze query plan: {str(e)}")
            return {}
    
    @staticmethod
    def suggest_indexes(db: Session, table_name: str) -> List[str]:
        """Suggest missing indexes based on query patterns"""
        suggestions = []
        
        # This is a simplified version - in production, you'd analyze actual query logs
        common_patterns = {
            'users': [
                "CREATE INDEX CONCURRENTLY idx_users_email_active ON users(email, is_active) WHERE is_deleted = false;",
                "CREATE INDEX CONCURRENTLY idx_users_created_city ON users(created_at, city) WHERE is_active = true;"
            ],
            'events': [
                "CREATE INDEX CONCURRENTLY idx_events_creator_status_date ON events(creator_id, status, start_datetime);",
                "CREATE INDEX CONCURRENTLY idx_events_location_type ON events(venue_city, event_type) WHERE is_public = true;"
            ],
            'notifications': [
                "CREATE INDEX CONCURRENTLY idx_notifications_recipient_status_type ON notification_logs(recipient_id, status, notification_type);",
                "CREATE INDEX CONCURRENTLY idx_notifications_sent_channel ON notification_logs(sent_at, channel) WHERE status = 'delivered';"
            ]
        }
        
        return common_patterns.get(table_name, [])
    
    @staticmethod
    def check_table_bloat(db: Session, table_name: str) -> Dict:
        """Check table bloat (PostgreSQL specific)"""
        try:
            bloat_query = """
            SELECT 
                schemaname, tablename, 
                pg_size_pretty(table_bytes) AS table_size,
                pg_size_pretty(bloat_bytes) AS bloat_size,
                round(bloat_bytes::numeric / table_bytes::numeric * 100, 2) AS bloat_pct
            FROM (
                SELECT 
                    schemaname, tablename,
                    pg_total_relation_size(schemaname||'.'||tablename) AS table_bytes,
                    (pg_total_relation_size(schemaname||'.'||tablename) - 
                     pg_relation_size(schemaname||'.'||tablename)) AS bloat_bytes
                FROM pg_tables 
                WHERE tablename = :table_name
            ) AS bloat_data;
            """
            
            result = db.execute(text(bloat_query), {'table_name': table_name}).fetchone()
            if result:
                return {
                    'table_size': result.table_size,
                    'bloat_size': result.bloat_size,
                    'bloat_percentage': float(result.bloat_pct)
                }
        except Exception as e:
            perf_logger.error(f"Failed to check table bloat: {str(e)}")
        
        return {}

# SQLAlchemy event listeners for performance monitoring
@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Record query start time"""
    context._query_start_time = time.time()

@event.listens_for(Engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Record query completion and log performance"""
    if hasattr(context, '_query_start_time'):
        duration = time.time() - context._query_start_time
        query_monitor.log_query(statement, duration, parameters)

@event.listens_for(Pool, "checkout")
def receive_checkout(dbapi_connection, connection_record, connection_proxy):
    """Track connection checkout"""
    pool_monitor.pool_stats['checked_out'] += 1

@event.listens_for(Pool, "checkin")
def receive_checkin(dbapi_connection, connection_record):
    """Track connection checkin"""
    pool_monitor.pool_stats['checked_in'] += 1

def get_performance_report() -> Dict:
    """Generate comprehensive performance report"""
    return {
        'query_stats': query_monitor.get_query_stats(),
        'slow_queries': query_monitor.get_slow_queries(),
        'pool_stats': pool_monitor.get_stats(),
        'pool_healthy': pool_monitor.is_pool_healthy(),
        'timestamp': datetime.utcnow().isoformat()
    }

def optimize_query_with_hints(query: Query, hints: List[str]) -> Query:
    """Add query optimization hints"""
    for hint in hints:
        if hint == 'use_index':
            # This would be database-specific
            pass
        elif hint == 'force_join_order':
            # This would be database-specific
            pass
    return query

# Performance testing utilities
class PerformanceTest:
    """Utilities for performance testing database operations"""
    
    @staticmethod
    def benchmark_query(db: Session, query_func: Callable, iterations: int = 10) -> Dict:
        """Benchmark a query function"""
        durations = []
        
        for _ in range(iterations):
            start_time = time.time()
            try:
                result = query_func(db)
                duration = time.time() - start_time
                durations.append(duration)
            except Exception as e:
                perf_logger.error(f"Benchmark query failed: {str(e)}")
                continue
        
        if durations:
            return {
                'avg_duration': sum(durations) / len(durations),
                'min_duration': min(durations),
                'max_duration': max(durations),
                'total_duration': sum(durations),
                'iterations': len(durations)
            }
        
        return {'error': 'All benchmark iterations failed'}
    
    @staticmethod
    def load_test_connection_pool(db_session_factory, concurrent_requests: int = 50):
        """Test connection pool under load"""
        import concurrent.futures
        import threading
        
        results = []
        
        def make_request():
            start_time = time.time()
            try:
                with db_session_factory() as db:
                    # Simple query to test connection
                    db.execute(text("SELECT 1")).fetchone()
                    return time.time() - start_time
            except Exception as e:
                return {'error': str(e), 'duration': time.time() - start_time}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
            futures = [executor.submit(make_request) for _ in range(concurrent_requests)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        successful_requests = [r for r in results if not isinstance(r, dict)]
        failed_requests = [r for r in results if isinstance(r, dict)]
        
        return {
            'total_requests': concurrent_requests,
            'successful_requests': len(successful_requests),
            'failed_requests': len(failed_requests),
            'avg_response_time': sum(successful_requests) / len(successful_requests) if successful_requests else 0,
            'max_response_time': max(successful_requests) if successful_requests else 0,
            'errors': failed_requests
        }