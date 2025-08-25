#!/usr/bin/env python3
"""
데이터 정리 스크립트 - 크롤링된 모든 데이터를 삭제합니다.
"""
import os
import shutil
import asyncio
import redis
from datetime import datetime, date
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import sys

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.models.database import ExtractionJob, CacheEntry, SystemMetric, AuditLog
from app.db.session import get_db

class DataCleaner:
    def __init__(self):
        self.redis_client = None
        self.db_engine = None
        
    async def setup_connections(self):
        """연결 설정"""
        # Redis 연결
        if settings.REDIS_URL:
            try:
                self.redis_client = redis.from_url(settings.REDIS_URL)
                self.redis_client.ping()
                print("✅ Redis 연결 성공")
            except Exception as e:
                print(f"❌ Redis 연결 실패: {e}")
        
        # 데이터베이스 연결
        if settings.DATABASE_URL:
            try:
                self.db_engine = create_engine(settings.DATABASE_URL)
                print("✅ 데이터베이스 연결 성공")
            except Exception as e:
                print(f"❌ 데이터베이스 연결 실패: {e}")
    
    def clean_files_and_directories(self, target_date: date = None):
        """파일 시스템 정리"""
        print(f"\n🗂️  파일 시스템 정리 중...")
        
        directories_to_clean = [
            "output",
            "outputs", 
            "storage/uploads",
            "storage/converted",
            "temp",
            "uploads"
        ]
        
        cleaned_files = 0
        cleaned_dirs = []
        
        for directory in directories_to_clean:
            dir_path = Path(directory)
            if dir_path.exists():
                try:
                    if target_date:
                        # 특정 날짜의 파일만 삭제
                        for file_path in dir_path.rglob("*"):
                            if file_path.is_file():
                                file_date = date.fromtimestamp(file_path.stat().st_mtime)
                                if file_date == target_date:
                                    file_path.unlink()
                                    cleaned_files += 1
                                    print(f"  삭제됨: {file_path}")
                    else:
                        # 모든 파일 삭제 (디렉토리는 유지)
                        for file_path in dir_path.rglob("*"):
                            if file_path.is_file() and file_path.name != ".gitkeep":
                                file_path.unlink()
                                cleaned_files += 1
                                print(f"  삭제됨: {file_path}")
                    
                    cleaned_dirs.append(str(directory))
                except Exception as e:
                    print(f"  ❌ {directory} 정리 실패: {e}")
        
        print(f"✅ 파일 정리 완료: {cleaned_files}개 파일 삭제")
        return cleaned_files, cleaned_dirs
    
    def clean_redis_cache(self, target_date: date = None):
        """Redis 캐시 정리"""
        if not self.redis_client:
            print("⚠️  Redis 연결이 없어 캐시 정리를 건너뜁니다.")
            return 0
        
        print(f"\n🗄️  Redis 캐시 정리 중...")
        
        try:
            if target_date:
                # 특정 날짜의 캐시만 삭제 (구현이 복잡하므로 전체 삭제 권장)
                print("  특정 날짜 캐시 삭제는 복잡하므로 전체 캐시를 삭제합니다.")
            
            # 모든 캐시 키 가져오기
            keys = self.redis_client.keys("*")
            if keys:
                deleted_count = self.redis_client.delete(*keys)
                print(f"✅ Redis 캐시 정리 완료: {deleted_count}개 키 삭제")
                return deleted_count
            else:
                print("✅ 삭제할 캐시가 없습니다.")
                return 0
                
        except Exception as e:
            print(f"❌ Redis 캐시 정리 실패: {e}")
            return 0
    
    def clean_database(self, target_date: date = None):
        """데이터베이스 정리"""
        if not self.db_engine:
            print("⚠️  데이터베이스 연결이 없어 DB 정리를 건너뜁니다.")
            return {}
        
        print(f"\n🗃️  데이터베이스 정리 중...")
        
        cleaned_counts = {
            'extraction_jobs': 0,
            'cache_entries': 0,
            'system_metrics': 0,
            'audit_logs': 0
        }
        
        try:
            Session = sessionmaker(bind=self.db_engine)
            session = Session()
            
            if target_date:
                target_datetime = datetime.combine(target_date, datetime.min.time())
                next_day = datetime.combine(target_date, datetime.max.time())
                
                # 특정 날짜의 데이터만 삭제
                queries = [
                    (ExtractionJob, ExtractionJob.created_at.between(target_datetime, next_day)),
                    (CacheEntry, CacheEntry.created_at.between(target_datetime, next_day)),
                    (SystemMetric, SystemMetric.timestamp.between(target_datetime, next_day)),
                    (AuditLog, AuditLog.timestamp.between(target_datetime, next_day))
                ]
            else:
                # 모든 데이터 삭제
                queries = [
                    (ExtractionJob, None),
                    (CacheEntry, None),
                    (SystemMetric, None),
                    (AuditLog, None)
                ]
            
            for model, condition in queries:
                table_name = model.__tablename__
                try:
                    if condition is not None:
                        count = session.query(model).filter(condition).count()
                        session.query(model).filter(condition).delete()
                    else:
                        count = session.query(model).count()
                        session.query(model).delete()
                    
                    cleaned_counts[table_name] = count
                    print(f"  {table_name}: {count}개 레코드 삭제")
                    
                except Exception as e:
                    print(f"  ❌ {table_name} 정리 실패: {e}")
            
            session.commit()
            session.close()
            
            total_deleted = sum(cleaned_counts.values())
            print(f"✅ 데이터베이스 정리 완료: 총 {total_deleted}개 레코드 삭제")
            
        except Exception as e:
            print(f"❌ 데이터베이스 정리 실패: {e}")
        
        return cleaned_counts
    
    async def cleanup_all(self, target_date: date = None):
        """전체 데이터 정리"""
        print("🧹 데이터 정리를 시작합니다...")
        
        if target_date:
            print(f"📅 대상 날짜: {target_date}")
        else:
            print("📅 모든 데이터를 삭제합니다.")
        
        # 연결 설정
        await self.setup_connections()
        
        # 정리 실행
        file_count, cleaned_dirs = self.clean_files_and_directories(target_date)
        cache_count = self.clean_redis_cache(target_date)
        db_counts = self.clean_database(target_date)
        
        # 결과 요약
        print(f"\n📊 정리 결과 요약:")
        print(f"  📁 파일: {file_count}개 삭제")
        print(f"  🗄️  캐시: {cache_count}개 키 삭제")
        print(f"  🗃️  데이터베이스: {sum(db_counts.values())}개 레코드 삭제")
        print(f"  📂 정리된 디렉토리: {', '.join(cleaned_dirs)}")
        
        print(f"\n✅ 데이터 정리가 완료되었습니다!")

async def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="크롤링 데이터 정리 스크립트")
    parser.add_argument(
        "--date", 
        type=str, 
        help="삭제할 날짜 (YYYY-MM-DD 형식, 미지정시 모든 데이터 삭제)"
    )
    parser.add_argument(
        "--confirm", 
        action="store_true", 
        help="확인 없이 즉시 실행"
    )
    
    args = parser.parse_args()
    
    target_date = None
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print("❌ 날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력해주세요.")
            return
    
    # 확인 메시지
    if not args.confirm:
        if target_date:
            message = f"{target_date} 날짜의 데이터를 삭제하시겠습니까?"
        else:
            message = "모든 크롤링 데이터를 삭제하시겠습니까?"
        
        response = input(f"{message} (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("취소되었습니다.")
            return
    
    # 정리 실행
    cleaner = DataCleaner()
    await cleaner.cleanup_all(target_date)

if __name__ == "__main__":
    asyncio.run(main())
