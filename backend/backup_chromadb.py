"""
ChromaDB Backup System

Automated backup solution for ChromaDB with support for:
- Local file system backups
- Cloud storage (S3, compatible services)
- Backup retention management
- Restore functionality
- Scheduled execution via cron jobs

Usage:
    # Manual backup
    python backup_chromadb.py

    # Restore from backup
    python backup_chromadb.py --restore backup_20241225_120000

    # List available backups
    python backup_chromadb.py --list

    # Clean old backups
    python backup_chromadb.py --cleanup --keep 7
"""

import os
import shutil
import tarfile
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


class ChromaDBBackup:
    """Manages ChromaDB backups to local and cloud storage"""

    def __init__(
        self,
        chroma_db_path: str = "./chroma_data",
        backup_dir: str = "./backups",
        retention_days: int = 7,
        enable_s3: bool = False,
        s3_bucket: Optional[str] = None,
        aws_region: str = "us-east-1"
    ):
        """
        Initialize backup manager

        Args:
            chroma_db_path: Path to ChromaDB data directory
            backup_dir: Local directory for backups
            retention_days: Number of days to keep backups
            enable_s3: Enable S3 upload
            s3_bucket: S3 bucket name for cloud backups
            aws_region: AWS region for S3
        """
        self.chroma_db_path = Path(chroma_db_path)
        self.backup_dir = Path(backup_dir)
        self.retention_days = retention_days
        self.enable_s3 = enable_s3
        self.s3_bucket = s3_bucket
        self.aws_region = aws_region

        # Validate ChromaDB path
        if not self.chroma_db_path.exists():
            logger.error(f"ChromaDB path does not exist: {self.chroma_db_path}")
            raise FileNotFoundError(f"ChromaDB not found at {self.chroma_db_path}")

        # Create backup directory if it doesn't exist
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Backup directory: {self.backup_dir}")

        # Initialize S3 client if enabled
        self.s3_client = None
        if self.enable_s3:
            self._initialize_s3()

    def _initialize_s3(self):
        """Initialize AWS S3 client"""
        try:
            import boto3
            from botocore.exceptions import ClientError

            self.s3_client = boto3.client('s3', region_name=self.aws_region)

            # Verify bucket exists and is accessible
            try:
                self.s3_client.head_bucket(Bucket=self.s3_bucket)
                logger.info(f"✓ Connected to S3 bucket: {self.s3_bucket}")
            except ClientError as e:
                logger.error(f"S3 bucket not accessible: {e}")
                raise

        except ImportError:
            logger.error("boto3 not installed. Install with: pip install boto3")
            raise

    def create_backup(self, backup_name: Optional[str] = None) -> Path:
        """
        Create a compressed backup of ChromaDB

        Args:
            backup_name: Optional custom backup name

        Returns:
            Path to the backup file
        """
        if not backup_name:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_name = f"chroma_backup_{timestamp}"

        backup_file = self.backup_dir / f"{backup_name}.tar.gz"

        logger.info("=" * 60)
        logger.info(f"Creating backup: {backup_name}")
        logger.info(f"Source: {self.chroma_db_path}")
        logger.info(f"Destination: {backup_file}")
        logger.info("=" * 60)

        try:
            # Calculate source size
            total_size = sum(
                f.stat().st_size for f in self.chroma_db_path.rglob('*') if f.is_file()
            )
            logger.info(f"ChromaDB size: {total_size / 1024**2:.2f} MB")

            # Create tar.gz archive
            with tarfile.open(backup_file, "w:gz") as tar:
                tar.add(self.chroma_db_path, arcname="chroma_data")

            # Verify backup
            backup_size = backup_file.stat().st_size
            logger.info(f"✓ Backup created: {backup_size / 1024**2:.2f} MB")
            logger.info(f"Compression ratio: {backup_size / total_size * 100:.1f}%")

            # Upload to S3 if enabled
            if self.enable_s3 and self.s3_client:
                self._upload_to_s3(backup_file, backup_name)

            # Cleanup old backups
            self._cleanup_old_backups()

            logger.info("=" * 60)
            logger.info("✅ Backup completed successfully!")
            logger.info("=" * 60)

            return backup_file

        except Exception as e:
            logger.error(f"❌ Backup failed: {e}", exc_info=True)
            # Clean up partial backup
            if backup_file.exists():
                backup_file.unlink()
            raise

    def _upload_to_s3(self, backup_file: Path, backup_name: str):
        """Upload backup to S3"""
        try:
            s3_key = f"chromadb_backups/{backup_name}.tar.gz"
            logger.info(f"Uploading to S3: s3://{self.s3_bucket}/{s3_key}")

            self.s3_client.upload_file(
                str(backup_file),
                self.s3_bucket,
                s3_key,
                ExtraArgs={
                    'StorageClass': 'STANDARD_IA',  # Infrequent Access = cheaper
                    'ServerSideEncryption': 'AES256'  # Encrypt at rest
                }
            )

            logger.info(f"✓ Uploaded to S3: {s3_key}")

        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            # Don't fail the entire backup if S3 upload fails
            logger.warning("Continuing with local backup only")

    def _cleanup_old_backups(self):
        """Remove backups older than retention period"""
        try:
            backups = sorted(self.backup_dir.glob("chroma_backup_*.tar.gz"))

            if len(backups) <= self.retention_days:
                logger.info(f"Keeping all {len(backups)} backups (within retention)")
                return

            # Keep only the most recent backups
            to_delete = backups[:-self.retention_days]

            for backup_file in to_delete:
                logger.info(f"Removing old backup: {backup_file.name}")
                backup_file.unlink()

            logger.info(f"✓ Cleaned up {len(to_delete)} old backups")

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            # Don't fail the backup process if cleanup fails

    def restore_backup(self, backup_name: str, target_path: Optional[str] = None):
        """
        Restore ChromaDB from a backup

        Args:
            backup_name: Name of the backup to restore (with or without .tar.gz)
            target_path: Optional custom restore location
        """
        if not backup_name.endswith('.tar.gz'):
            backup_name = f"{backup_name}.tar.gz"

        backup_file = self.backup_dir / backup_name

        if not backup_file.exists():
            logger.error(f"Backup not found: {backup_file}")
            raise FileNotFoundError(f"Backup not found: {backup_name}")

        target_path = Path(target_path) if target_path else self.chroma_db_path

        logger.info("=" * 60)
        logger.info(f"Restoring backup: {backup_name}")
        logger.info(f"Source: {backup_file}")
        logger.info(f"Target: {target_path}")
        logger.info("=" * 60)

        try:
            # Backup current data if it exists
            if target_path.exists():
                backup_current = target_path.parent / f"{target_path.name}.backup"
                logger.info(f"Backing up current data to: {backup_current}")
                if backup_current.exists():
                    shutil.rmtree(backup_current)
                shutil.copytree(target_path, backup_current)

            # Remove current data
            if target_path.exists():
                shutil.rmtree(target_path)

            # Extract backup
            with tarfile.open(backup_file, "r:gz") as tar:
                tar.extractall(target_path.parent)

            logger.info("✅ Restore completed successfully!")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"❌ Restore failed: {e}", exc_info=True)
            raise

    def list_backups(self) -> List[dict]:
        """List all available backups"""
        backups = sorted(
            self.backup_dir.glob("chroma_backup_*.tar.gz"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        backup_list = []
        for backup_file in backups:
            stat = backup_file.stat()
            backup_list.append({
                "name": backup_file.stem,
                "filename": backup_file.name,
                "size_mb": round(stat.st_size / 1024**2, 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "age_days": (datetime.now(timezone.utc).timestamp() - stat.st_mtime) / 86400
            })

        return backup_list

    def verify_backup(self, backup_name: str) -> bool:
        """
        Verify backup integrity

        Args:
            backup_name: Name of the backup to verify

        Returns:
            True if backup is valid
        """
        if not backup_name.endswith('.tar.gz'):
            backup_name = f"{backup_name}.tar.gz"

        backup_file = self.backup_dir / backup_name

        if not backup_file.exists():
            logger.error(f"Backup not found: {backup_file}")
            return False

        try:
            with tarfile.open(backup_file, "r:gz") as tar:
                # Try to read all members
                members = tar.getmembers()
                logger.info(f"Backup contains {len(members)} files")

                # Verify tar integrity
                tar.extract all=False  # Don't extract, just verify

            logger.info(f"✓ Backup verified: {backup_name}")
            return True

        except Exception as e:
            logger.error(f"❌ Backup verification failed: {e}")
            return False


def main():
    """Command-line interface for backup management"""
    parser = argparse.ArgumentParser(description="ChromaDB Backup Manager")
    parser.add_argument(
        "--restore",
        metavar="BACKUP_NAME",
        help="Restore from specified backup"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available backups"
    )
    parser.add_argument(
        "--verify",
        metavar="BACKUP_NAME",
        help="Verify backup integrity"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove old backups"
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=7,
        help="Number of backups to keep (default: 7)"
    )

    args = parser.parse_args()

    # Load configuration from environment
    chroma_db_path = os.getenv("CHROMA_DB_PATH", "./chroma_data")
    backup_dir = os.getenv("BACKUP_DIR", "./backups")
    retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", args.keep))
    enable_s3 = os.getenv("ENABLE_AUTO_BACKUP", "false").lower() == "true"
    s3_bucket = os.getenv("S3_BACKUP_BUCKET")
    aws_region = os.getenv("AWS_REGION", "us-east-1")

    # Initialize backup manager
    try:
        backup_manager = ChromaDBBackup(
            chroma_db_path=chroma_db_path,
            backup_dir=backup_dir,
            retention_days=retention_days,
            enable_s3=enable_s3 and s3_bucket is not None,
            s3_bucket=s3_bucket,
            aws_region=aws_region
        )

        # Execute requested action
        if args.restore:
            backup_manager.restore_backup(args.restore)

        elif args.list:
            backups = backup_manager.list_backups()
            if not backups:
                print("No backups found")
            else:
                print("\n=== Available Backups ===\n")
                for backup in backups:
                    print(f"Name:    {backup['name']}")
                    print(f"Size:    {backup['size_mb']} MB")
                    print(f"Created: {backup['created_at']}")
                    print(f"Age:     {backup['age_days']:.1f} days")
                    print("-" * 40)

        elif args.verify:
            success = backup_manager.verify_backup(args.verify)
            exit(0 if success else 1)

        elif args.cleanup:
            backup_manager._cleanup_old_backups()

        else:
            # Default action: create backup
            backup_manager.create_backup()

    except Exception as e:
        logger.error(f"Operation failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()
