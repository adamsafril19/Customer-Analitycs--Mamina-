"""
Script untuk mengecek koneksi database PostgreSQL
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Load .env dari folder backend
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

def check_database_connection():
    """Test database connection"""
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    if not DATABASE_URL:
        print("❌ ERROR: DATABASE_URL tidak ditemukan di .env")
        return False
    
    print(f"📍 Database URL: {DATABASE_URL[:30]}...")
    print("🔄 Mencoba koneksi ke PostgreSQL...")
    
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        
        with engine.connect() as conn:
            # Test basic connection
            result = conn.execute(text("SELECT 1"))
            print("✅ Koneksi berhasil! SELECT 1 ->", result.scalar())
            
            # Get PostgreSQL version
            version_result = conn.execute(text("SELECT version()"))
            version = version_result.scalar()
            print(f"✅ PostgreSQL Version: {version[:50]}...")
            
            # Check current database
            db_result = conn.execute(text("SELECT current_database()"))
            db_name = db_result.scalar()
            print(f"✅ Database aktif: {db_name}")
            
            # Check current user
            user_result = conn.execute(text("SELECT current_user"))
            user = user_result.scalar()
            print(f"✅ User: {user}")
            
            return True
            
    except SQLAlchemyError as e:
        print(f"❌ ERROR koneksi database: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR tidak terduga: {e}")
        return False

def check_redis_connection():
    """Test Redis connection"""
    REDIS_URL = os.getenv("REDIS_URL")
    
    if not REDIS_URL:
        print("⚠️ WARNING: REDIS_URL tidak ditemukan di .env")
        return False
    
    print(f"\n📍 Redis URL: {REDIS_URL}")
    print("🔄 Mencoba koneksi ke Redis...")
    
    try:
        import redis
        r = redis.from_url(REDIS_URL)
        
        # Test PING
        if r.ping():
            print("✅ Redis PING berhasil!")
            
            # Test SET/GET
            r.set("health:check", "ok")
            val = r.get("health:check")
            print(f"✅ Redis SET/GET berhasil: {val}")
            r.delete("health:check")
            
            return True
        else:
            print("❌ Redis PING gagal")
            return False
            
    except ImportError:
        print("⚠️ Redis library tidak terinstall")
        return False
    except Exception as e:
        print(f"❌ ERROR koneksi Redis: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("🔍 CEK KONEKSI DATABASE & REDIS")
    print("=" * 50)
    
    db_ok = check_database_connection()
    redis_ok = check_redis_connection()
    
    print("\n" + "=" * 50)
    print("📊 RINGKASAN:")
    print(f"   Database PostgreSQL: {'✅ OK' if db_ok else '❌ GAGAL'}")
    print(f"   Redis: {'✅ OK' if redis_ok else '❌ GAGAL'}")
    print("=" * 50)
    
    if not db_ok:
        print("\n💡 Tips jika koneksi database gagal:")
        print("   1. Pastikan PostgreSQL service berjalan")
        print("   2. Cek host, port, username, password di DATABASE_URL")
        print("   3. Pastikan database sudah dibuat")
        print("   4. Cek firewall/pg_hba.conf jika perlu")
    
    if not redis_ok:
        print("\n💡 Tips jika koneksi Redis gagal:")
        print("   1. Pastikan Redis server berjalan")
        print("   2. Cek host dan port di REDIS_URL")
        print("   3. Jika pakai Docker: docker run -d -p 6379:6379 redis:7")
    
    sys.exit(0 if db_ok else 1)
