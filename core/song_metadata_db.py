"""
楽曲メタデータのMySQL管理モジュール

ベクトルDBから分離された楽曲メタデータをMySQL側で管理する。
"""

from datetime import datetime
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from core.models import Song, ProcessedCollection
from core.database import get_session


def add_song(
    song_id: str,
    filename: str,
    song_title: str,
    artist_name: str = "",
    source_dir: str = "",
    youtube_id: str = "",
    file_extension: str = "",
    file_size_mb: float = 0.0,
    excluded_from_search: bool = False,
) -> None:
    """
    楽曲メタデータをMySQLに登録する

    Args:
        song_id: 楽曲の一意なID
        filename: ファイル名
        song_title: 曲名
        artist_name: アーティスト名
        source_dir: ソースディレクトリ
        youtube_id: YouTube動画ID
        file_extension: ファイル拡張子
        file_size_mb: ファイルサイズ（MB）
        excluded_from_search: 検索除外フラグ
    """
    with get_session() as session:
        song = Song(
            song_id=song_id,
            filename=filename,
            song_title=song_title,
            artist_name=artist_name,
            source_dir=source_dir,
            youtube_id=youtube_id,
            file_extension=file_extension,
            file_size_mb=file_size_mb,
            registered_at=datetime.now(),
            excluded_from_search=excluded_from_search,
        )
        session.add(song)


def get_song(song_id: str) -> dict | None:
    """
    楽曲メタデータを取得する

    Args:
        song_id: 楽曲ID

    Returns:
        楽曲情報の辞書（見つからない場合はNone）
    """
    with get_session() as session:
        stmt = select(Song).where(Song.song_id == song_id)
        result = session.execute(stmt).scalar_one_or_none()
        if result:
            # セッション内で辞書に変換
            return {
                "song_id": result.song_id,
                "filename": result.filename,
                "song_title": result.song_title,
                "artist_name": result.artist_name,
                "source_dir": result.source_dir,
                "youtube_id": result.youtube_id,
                "file_extension": result.file_extension,
                "file_size_mb": result.file_size_mb,
                "registered_at": result.registered_at.isoformat(),
                "excluded_from_search": result.excluded_from_search,
            }
        return None


def get_songs(song_ids: list[str]) -> list[dict]:
    """
    複数の楽曲メタデータを一括取得する

    Args:
        song_ids: 楽曲IDのリスト

    Returns:
        楽曲情報の辞書のリスト
    """
    if not song_ids:
        return []

    with get_session() as session:
        stmt = select(Song).where(Song.song_id.in_(song_ids))
        results = list(session.execute(stmt).scalars().all())
        # セッション内で辞書に変換
        return [
            {
                "song_id": song.song_id,
                "filename": song.filename,
                "song_title": song.song_title,
                "artist_name": song.artist_name,
                "source_dir": song.source_dir,
                "youtube_id": song.youtube_id,
                "file_extension": song.file_extension,
                "file_size_mb": song.file_size_mb,
                "registered_at": song.registered_at.isoformat(),
                "excluded_from_search": song.excluded_from_search,
            }
            for song in results
        ]


def get_by_youtube_id(youtube_id: str) -> dict | None:
    """
    YouTube動画IDで楽曲を検索する

    Args:
        youtube_id: YouTube動画ID（11文字）

    Returns:
        楽曲情報の辞書（見つからない場合はNone）
    """
    with get_session() as session:
        stmt = select(Song).where(Song.youtube_id == youtube_id)
        result = session.execute(stmt).scalar_one_or_none()
        if result:
            # セッション内で辞書に変換
            return {
                "song_id": result.song_id,
                "filename": result.filename,
                "song_title": result.song_title,
                "artist_name": result.artist_name,
                "source_dir": result.source_dir,
                "youtube_id": result.youtube_id,
                "file_extension": result.file_extension,
                "file_size_mb": result.file_size_mb,
                "registered_at": result.registered_at.isoformat(),
                "excluded_from_search": result.excluded_from_search,
            }
        return None


def search_by_keyword(
    keyword: str, limit: int = 10000, exclude_from_search: bool = True
) -> list[tuple[str, dict]]:
    """
    キーワードでメタデータを部分一致検索する（SQL LIKE検索）

    Args:
        keyword: 検索キーワード
        limit: 最大取得件数
        exclude_from_search: 検索除外フラグがTrueの曲を除外するか

    Returns:
        (song_id, metadata_dict)のタプルのリスト
    """
    with get_session() as session:
        keyword_pattern = f"%{keyword}%"
        stmt = select(Song).where(
            or_(
                Song.song_id.like(keyword_pattern),
                Song.filename.like(keyword_pattern),
                Song.song_title.like(keyword_pattern),
                Song.artist_name.like(keyword_pattern),
                Song.source_dir.like(keyword_pattern),
            )
        )

        if exclude_from_search:
            stmt = stmt.where(Song.excluded_from_search == False)

        stmt = stmt.limit(limit)
        songs = list(session.execute(stmt).scalars().all())
        # セッション内で辞書に変換（detached instance エラーを防ぐ）
        results = [
            (
                song.song_id,
                {
                    "filename": song.filename,
                    "song_title": song.song_title,
                    "artist_name": song.artist_name,
                    "source_dir": song.source_dir,
                    "youtube_id": song.youtube_id,
                    "file_extension": song.file_extension,
                    "file_size_mb": song.file_size_mb,
                    "registered_at": song.registered_at.isoformat(),
                    "excluded_from_search": song.excluded_from_search,
                },
            )
            for song in songs
        ]
        return results


def update_excluded_from_search(song_id: str, excluded: bool) -> bool:
    """
    楽曲の検索除外フラグを更新する

    Args:
        song_id: 楽曲ID
        excluded: 検索除外フラグ

    Returns:
        更新に成功した場合True、楽曲が見つからない場合False
    """
    with get_session() as session:
        stmt = select(Song).where(Song.song_id == song_id)
        song = session.execute(stmt).scalar_one_or_none()
        if song:
            song.excluded_from_search = excluded
            session.commit()
            return True
        return False


def delete_song(song_id: str) -> bool:
    """
    楽曲メタデータを削除する

    Args:
        song_id: 楽曲ID

    Returns:
        削除に成功した場合True、楽曲が見つからない場合False
    """
    with get_session() as session:
        stmt = select(Song).where(Song.song_id == song_id)
        song = session.execute(stmt).scalar_one_or_none()
        if song:
            session.delete(song)
            return True
        return False


def count_songs(exclude_from_search: bool = False) -> int:
    """
    登録されている楽曲数を返す

    Args:
        exclude_from_search: 検索除外フラグがTrueの曲を除外してカウントするか

    Returns:
        楽曲数
    """
    from sqlalchemy import func

    with get_session() as session:
        stmt = select(func.count()).select_from(Song)
        if exclude_from_search:
            stmt = stmt.where(Song.excluded_from_search == False)
        return session.scalar(stmt) or 0


def list_all(
    limit: int = 100, exclude_from_search: bool = False
) -> list[tuple[str, dict]]:
    """
    登録されている楽曲一覧を取得する

    Args:
        limit: 取得件数上限
        exclude_from_search: 検索除外フラグがTrueの曲を除外するか

    Returns:
        (song_id, metadata_dict)のタプルのリスト
    """
    with get_session() as session:
        stmt = select(Song)
        if exclude_from_search:
            stmt = stmt.where(Song.excluded_from_search == False)
        stmt = stmt.limit(limit)
        songs = list(session.execute(stmt).scalars().all())
        # セッション内で辞書に変換（detached instance エラーを防ぐ）
        results = [
            (
                song.song_id,
                {
                    "filename": song.filename,
                    "song_title": song.song_title,
                    "artist_name": song.artist_name,
                    "source_dir": song.source_dir,
                    "youtube_id": song.youtube_id,
                    "file_extension": song.file_extension,
                    "file_size_mb": song.file_size_mb,
                    "registered_at": song.registered_at.isoformat(),
                    "excluded_from_search": song.excluded_from_search,
                },
            )
            for song in songs
        ]
        return results


# === ProcessedCollection 関連の関数 ===


def mark_as_processed(song_id: str, collection_name: str) -> None:
    """
    楽曲を指定コレクションで処理済みとしてマークする

    Args:
        song_id: 楽曲ID
        collection_name: コレクション名
    """
    with get_session() as session:
        # 既に存在する場合は何もしない（unique制約で重複防止）
        stmt = select(ProcessedCollection).where(
            ProcessedCollection.song_id == song_id,
            ProcessedCollection.collection_name == collection_name,
        )
        existing = session.execute(stmt).scalar_one_or_none()
        if not existing:
            processed = ProcessedCollection(
                song_id=song_id,
                collection_name=collection_name,
                processed_at=datetime.now(),
            )
            session.add(processed)


def is_processed(song_id: str, collection_name: str) -> bool:
    """
    楽曲が指定コレクションで処理済みかチェックする

    Args:
        song_id: 楽曲ID
        collection_name: コレクション名

    Returns:
        処理済みの場合True
    """
    with get_session() as session:
        stmt = select(ProcessedCollection).where(
            ProcessedCollection.song_id == song_id,
            ProcessedCollection.collection_name == collection_name,
        )
        return session.execute(stmt).scalar_one_or_none() is not None


def get_processed_collections(song_id: str) -> list[str]:
    """
    楽曲が処理済みのコレクション名一覧を取得する

    Args:
        song_id: 楽曲ID

    Returns:
        処理済みコレクション名のリスト
    """
    with get_session() as session:
        stmt = select(ProcessedCollection.collection_name).where(
            ProcessedCollection.song_id == song_id
        )
        return list(session.execute(stmt).scalars().all())


def unmark_as_processed(song_id: str, collection_name: str) -> bool:
    """
    楽曲の処理済みフラグを削除する

    Args:
        song_id: 楽曲ID
        collection_name: コレクション名

    Returns:
        削除に成功した場合True
    """
    with get_session() as session:
        stmt = select(ProcessedCollection).where(
            ProcessedCollection.song_id == song_id,
            ProcessedCollection.collection_name == collection_name,
        )
        processed = session.execute(stmt).scalar_one_or_none()
        if processed:
            session.delete(processed)
            return True
        return False


def get_songs_as_dict(song_ids: list[str]) -> dict[str, dict]:
    """
    複数の楽曲メタデータを辞書形式で取得する（高速ルックアップ用）

    Args:
        song_ids: 楽曲IDのリスト

    Returns:
        {song_id: metadata_dict} の辞書
    """
    songs = get_songs(song_ids)
    return {song_dict["song_id"]: song_dict for song_dict in songs}
