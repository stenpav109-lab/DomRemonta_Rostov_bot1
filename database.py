import sqlite3
from datetime import datetime, timedelta
import os


class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Инициализация базы данных"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Таблица лидов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE,
                    name TEXT,
                    phone TEXT,
                    geography TEXT,
                    object_type TEXT,
                    condition TEXT,
                    metrage INTEGER,
                    repair_format TEXT,
                    keys_ready TEXT,
                    deadline TEXT,
                    main_fear TEXT,
                    budget TEXT,
                    source TEXT,
                    appointment_time TEXT,
                    appointment_status TEXT DEFAULT 'pending',
                    survey_completed INTEGER DEFAULT 0,
                    start_time TIMESTAMP,
                    created_at TIMESTAMP
                )
            """)

            # Таблица для хранения фото рассылок
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS broadcast_media (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    broadcast_type TEXT UNIQUE,
                    photo_file_id TEXT,
                    caption TEXT,
                    updated_at TIMESTAMP
                )
            """)

            conn.commit()

    def save_lead(self, data):
        """Сохранение лида"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO leads 
                (user_id, name, phone, geography, object_type, condition, metrage, 
                 repair_format, keys_ready, deadline, main_fear, budget, source, 
                 appointment_time, appointment_status, survey_completed, start_time, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['user_id'],
                data.get('name', ''),
                data.get('phone', ''),
                data.get('geography', ''),
                data.get('object_type', ''),
                data.get('condition', ''),
                data.get('metrage', 0),
                data.get('repair_format', ''),
                data.get('keys_ready', ''),
                data.get('deadline', ''),
                data.get('main_fear', ''),
                data.get('budget', ''),
                data.get('source', 'direct'),
                data.get('appointment_time', ''),
                data.get('appointment_status', 'pending'),
                data.get('survey_completed', 0),
                data.get('start_time'),
                datetime.now()
            ))
            conn.commit()

    def update_start_time(self, user_id):
        """Обновление времени старта"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            now = datetime.now()

            cursor.execute("""
                INSERT OR REPLACE INTO leads (user_id, start_time, created_at, survey_completed)
                VALUES (?, ?, ?, ?)
            """, (user_id, now, now, 0))

            conn.commit()
            return now

    def get_user_start_time(self, user_id):
        """Получение времени старта"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT start_time FROM leads WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else None

    def is_survey_completed(self, user_id):
        """Проверка, заполнена ли анкета"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT survey_completed FROM leads WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return result[0] == 1 if result else False

    def save_broadcast_media(self, broadcast_type, photo_file_id, caption):
        """Сохранение медиа для рассылки"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO broadcast_media 
                (broadcast_type, photo_file_id, caption, updated_at)
                VALUES (?, ?, ?, ?)
            """, (broadcast_type, photo_file_id, caption, datetime.now()))
            conn.commit()
            return True

    def get_broadcast_media(self, broadcast_type):
        """Получение медиа для рассылки"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT photo_file_id, caption FROM broadcast_media 
                WHERE broadcast_type = ?
            """, (broadcast_type,))
            result = cursor.fetchone()
            return result if result else None

    def get_all_users_with_start_time(self):
        """Получение всех пользователей, не заполнивших анкету"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, start_time, name, phone
                FROM leads 
                WHERE start_time IS NOT NULL AND survey_completed = 0
                ORDER BY start_time DESC
            """)
            return cursor.fetchall()

    def get_all_user_ids(self):
        """Получение ID всех пользователей"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM leads")
            return [row[0] for row in cursor.fetchall()]

    def get_all_users_without_survey(self):
        """Получение ID пользователей, не заполнивших анкету"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM leads WHERE survey_completed = 0 OR survey_completed IS NULL")
            return [row[0] for row in cursor.fetchall()]