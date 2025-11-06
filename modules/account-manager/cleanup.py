"""
账号自动清理模块 - 失效账号识别和清理
"""
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from shared.database.init import db
from shared.utils.logger import logger


class AccountCleanup:
    """账号自动清理管理器"""

    async def mark_expired_accounts(self, days_threshold: int = 30) -> int:
        """
        标记失效账号（软删除）

        Args:
            days_threshold: 未检查天数阈值

        Returns:
            标记数量
        """
        try:
            threshold_date = datetime.now() - timedelta(days=days_threshold)

            query = """
                UPDATE accounts
                SET status = 'expired', updated_at = ?
                WHERE status = 'active'
                AND (last_check < ? OR last_check IS NULL)
            """

            cursor = db.execute(query, (datetime.now(), threshold_date))
            count = cursor.rowcount

            logger.info(f"✅ 标记了 {count} 个失效账号")
            return count

        except Exception as e:
            logger.error(f"标记失效账号失败: {str(e)}")
            return 0

    async def archive_old_accounts(self, days_threshold: int = 90) -> int:
        """
        归档旧账号到历史表

        Args:
            days_threshold: 失效天数阈值

        Returns:
            归档数量
        """
        try:
            threshold_date = datetime.now() - timedelta(days=days_threshold)

            # 1. 创建归档表（如果不存在）
            db.execute("""
                CREATE TABLE IF NOT EXISTS accounts_archive (
                    LIKE accounts INCLUDING ALL
                )
            """)

            # 2. 复制到归档表
            db.execute("""
                INSERT INTO accounts_archive
                SELECT * FROM accounts
                WHERE status IN ('expired', 'banned')
                AND updated_at < ?
            """, (threshold_date,))

            # 3. 从主表删除
            cursor = db.execute("""
                DELETE FROM accounts
                WHERE status IN ('expired', 'banned')
                AND updated_at < ?
            """, (threshold_date,))

            count = cursor.rowcount
            db.conn.commit()

            logger.info(f"✅ 归档了 {count} 个旧账号")
            return count

        except Exception as e:
            logger.error(f"归档旧账号失败: {str(e)}")
            return 0

    async def cleanup_expired_accounts(
        self,
        delete_files: bool = True,
        delete_database: bool = False,
        days_threshold: int = 90
    ) -> Dict:
        """
        清理失效账号

        Args:
            delete_files: 是否删除物理文件（session文件）
            delete_database: 是否从数据库删除记录
            days_threshold: 失效天数阈值

        Returns:
            清理统计信息
        """
        try:
            threshold_date = datetime.now() - timedelta(days=days_threshold)

            # 查询失效账号
            query = """
                SELECT id, phone, session_type, status, updated_at
                FROM accounts
                WHERE status IN ('expired', 'banned')
                AND updated_at < ?
            """

            expired_accounts = db.fetchall(query, (threshold_date,))

            cleanup_stats = {
                "total": len(expired_accounts),
                "files_deleted": 0,
                "db_records_deleted": 0,
                "errors": []
            }

            logger.info(f"🗑️ 开始清理 {cleanup_stats['total']} 个失效账号...")

            for account in expired_accounts:
                account_id = account['id']
                phone = account['phone']

                try:
                    # 1. 删除物理文件
                    if delete_files:
                        deleted = await self._delete_account_files(phone)
                        if deleted:
                            cleanup_stats["files_deleted"] += 1

                    # 2. 删除数据库记录
                    if delete_database:
                        db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
                        cleanup_stats["db_records_deleted"] += 1

                except Exception as e:
                    error_msg = f"清理账号 {phone} 失败: {str(e)}"
                    logger.error(error_msg)
                    cleanup_stats["errors"].append(error_msg)

            # 提交数据库更改
            if delete_database:
                db.conn.commit()

            logger.info(f"✅ 清理完成: {cleanup_stats}")
            return cleanup_stats

        except Exception as e:
            logger.error(f"清理失效账号失败: {str(e)}")
            return {"error": str(e)}

    async def _delete_account_files(self, phone: str) -> bool:
        """
        删除账号相关的所有物理文件

        Args:
            phone: 手机号

        Returns:
            是否成功删除
        """
        deleted = False

        try:
            # 删除session文件
            session_patterns = [
                f"sessions/{phone}.session",
                f"sessions/{phone}.json",
                f"sessions/{phone}_tdata",
            ]

            for pattern in session_patterns:
                file_path = Path(pattern)

                if file_path.exists():
                    try:
                        if file_path.is_file():
                            os.remove(file_path)
                            deleted = True
                            logger.debug(f"   删除文件: {file_path}")
                        elif file_path.is_dir():
                            shutil.rmtree(file_path)
                            deleted = True
                            logger.debug(f"   删除目录: {file_path}")
                    except Exception as e:
                        logger.error(f"   删除失败 {file_path}: {str(e)}")

        except Exception as e:
            logger.error(f"删除账号文件失败: {str(e)}")

        return deleted

    async def get_cleanup_stats(self) -> Dict:
        """
        获取清理统计信息

        Returns:
            统计信息字典
        """
        stats = {}

        # 失效账号数
        result = db.fetchone("""
            SELECT COUNT(*) as count FROM accounts
            WHERE status IN ('expired', 'banned')
        """)
        stats['expired_count'] = result['count'] if result else 0

        # 30天未活跃账号数
        threshold_date = datetime.now() - timedelta(days=30)
        result = db.fetchone("""
            SELECT COUNT(*) as count FROM accounts
            WHERE status = 'active'
            AND (last_check < ? OR last_check IS NULL)
        """, (threshold_date,))
        stats['inactive_30days'] = result['count'] if result else 0

        # 90天未活跃账号数
        threshold_date = datetime.now() - timedelta(days=90)
        result = db.fetchone("""
            SELECT COUNT(*) as count FROM accounts
            WHERE status IN ('expired', 'banned')
            AND updated_at < ?
        """, (threshold_date,))
        stats['ready_for_cleanup'] = result['count'] if result else 0

        # 数据库大小
        result = db.fetchone("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        stats['database_size_mb'] = round(result['size'] / 1024 / 1024, 2) if result else 0

        return stats

    async def scheduled_cleanup(
        self,
        auto_mark: bool = True,
        auto_cleanup: bool = True,
        delete_files: bool = True,
        delete_database: bool = False
    ) -> Dict:
        """
        定时清理任务（完整流程）

        Args:
            auto_mark: 是否自动标记失效账号
            auto_cleanup: 是否自动清理
            delete_files: 是否删除文件
            delete_database: 是否删除数据库记录

        Returns:
            清理报告
        """
        logger.info("🕐 开始执行定时清理任务...")

        report = {
            "start_time": datetime.now().isoformat(),
            "marked_count": 0,
            "cleaned_count": 0,
            "files_deleted": 0,
            "db_records_deleted": 0
        }

        try:
            # 1. 标记失效账号（30天未检查）
            if auto_mark:
                marked = await self.mark_expired_accounts(days_threshold=30)
                report["marked_count"] = marked

            # 2. 清理90天前的失效账号
            if auto_cleanup:
                cleanup_stats = await self.cleanup_expired_accounts(
                    delete_files=delete_files,
                    delete_database=delete_database,
                    days_threshold=90
                )

                report["cleaned_count"] = cleanup_stats.get("total", 0)
                report["files_deleted"] = cleanup_stats.get("files_deleted", 0)
                report["db_records_deleted"] = cleanup_stats.get("db_records_deleted", 0)

            report["end_time"] = datetime.now().isoformat()
            report["status"] = "success"

            logger.info(f"✅ 定时清理完成: {report}")
            return report

        except Exception as e:
            error_msg = f"定时清理失败: {str(e)}"
            logger.error(error_msg)
            report["status"] = "failed"
            report["error"] = error_msg
            return report


# 全局实例
account_cleanup = AccountCleanup()


# 示例使用
async def example_usage():
    """示例：账号清理"""

    # 1. 获取清理统计
    print("📊 清理统计:")
    stats = await account_cleanup.get_cleanup_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # 2. 标记失效账号
    print("\n🏷️ 标记失效账号:")
    marked = await account_cleanup.mark_expired_accounts(days_threshold=30)
    print(f"  标记数量: {marked}")

    # 3. 清理失效账号
    print("\n🗑️ 清理失效账号:")
    cleanup_stats = await account_cleanup.cleanup_expired_accounts(
        delete_files=True,
        delete_database=False,
        days_threshold=90
    )
    print(f"  清理结果: {cleanup_stats}")

    # 4. 完整的定时清理
    print("\n🕐 执行定时清理:")
    report = await account_cleanup.scheduled_cleanup(
        auto_mark=True,
        auto_cleanup=True,
        delete_files=True,
        delete_database=False
    )
    print(f"  清理报告: {report}")


if __name__ == "__main__":
    import asyncio

    # 初始化数据库
    db.initialize()

    # 运行示例
    asyncio.run(example_usage())
