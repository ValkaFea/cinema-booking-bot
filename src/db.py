from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Any

# Файл базы данных будет лежать рядом с проектом
DB_PATH = Path("cinema.db")


@contextmanager
def get_conn():
    """Контекстный менеджер для соединения с SQLite."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Создаём таблицы и заполняем расписание, если его ещё нет."""
    with get_conn() as conn:
        cur = conn.cursor()

        # Таблица показов
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS screenings (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL,
                title TEXT NOT NULL,
                capacity INTEGER NOT NULL
            )
            """
        )

        # Таблица бронирований
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                screening_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                created_at TEXT NOT NULL,
                canceled_at TEXT,
                UNIQUE (screening_id, user_id)
            )
            """
        )

        # Стартовое расписание
        screenings_seed = [
            (1, "23.11", "Милая Френсис", 24),
            (2, "30.11", "Она", 24),
            (3, "07.12", "Перед рассветом", 24),
            (4, "14.12", "Амели", 24),
            (5, "21.12", "Вкус вишни", 24),
            (6, "28.12", "Париж, я люблю тебя", 24),
        ]

        # Вставим, только если таких id ещё нет
        cur.executemany(
            """
            INSERT OR IGNORE INTO screenings (id, date, title, capacity)
            VALUES (?, ?, ?, ?)
            """,
            screenings_seed,
        )

        conn.commit()


@dataclass
class ScreeningInfo:
    id: int
    date: str
    title: str
    capacity: int
    booked: int

    @property
    def free_places(self) -> int:
        return max(self.capacity - self.booked, 0)


@dataclass
class BookingInfo:
    id: int
    screening_id: int
    date: str
    title: str
    created_at: str


def get_screenings_with_stats() -> List[ScreeningInfo]:
    """Возвращает список показов с количеством занятых мест."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, date, title, capacity FROM screenings ORDER BY id"
        )
        rows = cur.fetchall()

        result: List[ScreeningInfo] = []
        for screening_id, date, title, capacity in rows:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM bookings
                WHERE screening_id = ? AND canceled_at IS NULL
                """,
                (screening_id,),
            )
            booked = cur.fetchone()[0] or 0
            result.append(
                ScreeningInfo(
                    id=screening_id,
                    date=date,
                    title=title,
                    capacity=capacity,
                    booked=booked,
                )
            )
        return result


def create_booking(
    screening_id: int,
    user_id: int,
    username: Optional[str],
    full_name: Optional[str],
) -> str:
    """
    Создаёт бронь.

    Возвращает строку-статус:
      - "already"      — если уже есть активная запись
      - "full"         — если мест нет
      - "ok"           — если успешно
      - "no_screening" — если показ не найден
    """
    with get_conn() as conn:
        cur = conn.cursor()

        # есть ли такой показ
        cur.execute(
            "SELECT capacity, date, title FROM screenings WHERE id = ?",
            (screening_id,),
        )
        row = cur.fetchone()
        if row is None:
            return "no_screening"

        capacity, date, title = row

        # уже записан?
        cur.execute(
            """
            SELECT id FROM bookings
            WHERE screening_id = ? AND user_id = ? AND canceled_at IS NULL
            """,
            (screening_id, user_id),
        )
        if cur.fetchone() is not None:
            return "already"

        # сколько уже записано
        cur.execute(
            """
            SELECT COUNT(*)
            FROM bookings
            WHERE screening_id = ? AND canceled_at IS NULL
            """,
            (screening_id,),
        )
        booked = cur.fetchone()[0] or 0
        if booked >= capacity:
            return "full"

        now = datetime.utcnow().isoformat(timespec="seconds")
        cur.execute(
            """
            INSERT INTO bookings (
                screening_id, user_id, username, full_name, created_at, canceled_at
            ) VALUES (?, ?, ?, ?, ?, NULL)
            """,
            (screening_id, user_id, username, full_name, now),
        )
        conn.commit()
        return "ok"


def get_user_bookings(user_id: int) -> List[BookingInfo]:
    """Возвращает все активные брони пользователя."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT b.id,
                   b.screening_id,
                   s.date,
                   s.title,
                   b.created_at
            FROM bookings b
            JOIN screenings s ON b.screening_id = s.id
            WHERE b.user_id = ? AND b.canceled_at IS NULL
            ORDER BY s.id
            """,
            (user_id,),
        )
        rows = cur.fetchall()

        return [
            BookingInfo(
                id=row[0],
                screening_id=row[1],
                date=row[2],
                title=row[3],
                created_at=row[4],
            )
            for row in rows
        ]


def cancel_booking(booking_id: int, user_id: int) -> bool:
    """
    Отменяет бронь.

    Возвращает True, если бронь реально была обновлена (отменена),
    и False, если такой активной брони не нашли.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat(timespec="seconds")
        cur.execute(
            """
            UPDATE bookings
            SET canceled_at = ?
            WHERE id = ? AND user_id = ? AND canceled_at IS NULL
            """,
            (now, booking_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0


def get_all_active_bookings() -> List[Tuple[Any, ...]]:
    """
    Возвращает список всех активных броней.
    Каждый элемент: (date, title, user_id, username, full_name, created_at)
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                s.date,
                s.title,
                b.user_id,
                b.username,
                b.full_name,
                b.created_at
            FROM bookings b
            JOIN screenings s ON s.id = b.screening_id
            WHERE b.canceled_at IS NULL
            ORDER BY s.id, b.created_at
            """
        )
        return cur.fetchall()


def add_screening(date: str, title: str, capacity: int) -> int:
    """Добавляет новый показ и возвращает его id."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO screenings (date, title, capacity) VALUES (?, ?, ?)",
            (date, title, capacity),
        )
        conn.commit()
        return cur.lastrowid


def update_screening(screening_id: int, date: str, title: str, capacity: int) -> bool:
    """Обновляет данные показа. Возвращает True, если что-то обновили."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE screenings
            SET date = ?, title = ?, capacity = ?
            WHERE id = ?
            """,
            (date, title, capacity, screening_id),
        )
        conn.commit()
        return cur.rowcount > 0


def delete_screening(screening_id: int) -> str:
    """
    Удаляет показ.

    Возвращает:
      - "ok"           — если успешно удалили
      - "has_bookings" — если на показ есть брони (не удаляем)
      - "not_found"    — если показа с таким id нет
    """
    with get_conn() as conn:
        cur = conn.cursor()

        # Проверяем, есть ли любые брони
        cur.execute(
            "SELECT COUNT(*) FROM bookings WHERE screening_id = ?",
            (screening_id,),
        )
        count = cur.fetchone()[0] or 0
        if count > 0:
            return "has_bookings"

        cur.execute("DELETE FROM screenings WHERE id = ?", (screening_id,))
        conn.commit()
        if cur.rowcount == 0:
            return "not_found"
        return "ok"
