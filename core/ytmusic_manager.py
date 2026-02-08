"""
YouTube Music プレイリスト管理モジュール
ytmusicapi を使用して、類似楽曲検索結果からプレイリストを自動作成する
"""

from typing import Literal
from ytmusicapi import YTMusic, OAuthCredentials, setup
import json
import time
import tempfile
import os


def load_secrets(secrets_file: str = "secrets.json") -> dict:
    """
    シークレット情報をファイルから読み込む

    Args:
        secrets_file: シークレットファイルのパス

    Returns:
        {"client_id": ..., "client_secret": ...}
    """
    with open(secrets_file, "r", encoding="utf-8") as f:
        return json.load(f)


class YTMusicManager:
    """YouTube Music API操作クラス"""

    def __init__(
        self,
        browser_file: str = "browser.json",
        oauth_dict: dict | None = None,
        access_token: str | None = None,
    ):
        """
        初期化

        Args:
            browser_file: ブラウザ認証ファイルのパス（後方互換性のため保持）
            oauth_dict: ユーザー固有のOAuth認証情報（辞書形式）
            access_token: Streamlitの st.user から取得したアクセストークン
        """
        if access_token:
            # Streamlit OAuth経由のアクセストークンを使用
            oauth_data = {
                "access_token": access_token,
                "token_type": "Bearer",
                # Note: refresh_token はStreamlitのOIDCでは提供されないため、
                # アクセストークンが期限切れになった場合はユーザーに再ログインを促す
            }
            
            # セキュアな一時ファイルを作成（ファイル権限を制限）
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".json", text=True)
            try:
                # ファイル権限を所有者のみ読み書き可能に設定
                os.chmod(tmp_path, 0o600)
                # ファイルディスクリプタを使用して書き込み
                with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                    json.dump(oauth_data, f)
                    f.flush()
                    os.fsync(f.fileno())
                
                self.yt = YTMusic(tmp_path)
            finally:
                # 確実に一時ファイルを削除
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        elif oauth_dict:
            # ユーザー固有のOAuth認証を使用（後方互換性）
            # 一時ファイルにOAuth情報を書き込んでYTMusicに渡す
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as tmp:
                json.dump(oauth_dict, tmp)
                tmp.flush()  # データが確実に書き込まれるようにする
                tmp_path = tmp.name

            try:
                self.yt = YTMusic(tmp_path)
            finally:
                # 一時ファイルを削除
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        else:
            # 後方互換性: browser.json を使用（レガシー）
            print("Using browser-based authentication (legacy mode)")
            self.yt = YTMusic(browser_file)

    def get_library_playlists(self) -> list[dict]:
        """
        自分のライブラリのプレイリスト一覧を取得

        Returns:
            プレイリストのリスト
        """
        return self.yt.get_library_playlists(limit=10)

    def find_playlist_by_name(self, name: str) -> str | None:
        """
        プレイリスト名からplaylistIdを取得

        Args:
            name: プレイリスト名

        Returns:
            playlistId（見つからない場合はNone）
        """
        playlists = self.get_library_playlists()
        for p in playlists:
            if p["title"] == name:
                return p["playlistId"]
        return None

    def _search_single(
        self, query: str, sleep_sec: float = 0.5
    ) -> dict[str, str] | None:
        """
        単一クエリでvideoIdを検索（内部用）

        Args:
            query: 検索クエリ
            sleep_sec: API呼び出し後のスリープ秒数

        Returns:
            {"videoId": ..., "title": ..., "artist": ...} または None
        """
        try:
            results = self.yt.search(query, filter="songs", limit=1)
            time.sleep(sleep_sec)  # レート制限対策

            if results and len(results) > 0:
                result = results[0]
                return {
                    "videoId": result.get("videoId"),
                    "title": result.get("title"),
                    "artist": (
                        result.get("artists", [{}])[0].get("name", "Unknown")
                        if result.get("artists")
                        else "Unknown"
                    ),
                }
        except Exception as e:
            print(f"Search error for '{query}': {e}")

        return None

    def search_video_id(
        self, query: str, sleep_sec: float = 0.5
    ) -> dict[str, str] | None:
        """
        クエリからvideoIdを検索（フォールバック付き）

        サフィックス（スペース区切りの最後の単語）付きで見つからない場合、
        サフィックスを除いて再検索する。

        Args:
            query: 検索クエリ（曲名、アーティスト名など）
            sleep_sec: API呼び出し後のスリープ秒数（レート制限対策）

        Returns:
            {"videoId": ..., "title": ..., "artist": ...} または None
        """
        # まず元のクエリで検索
        result = self._search_single(query, sleep_sec)
        if result:
            return result

        # 見つからない場合、サフィックス（最後の単語）を除いて再検索
        parts = query.rsplit(" ", 1)
        if len(parts) > 1:
            base_query = parts[0].strip()
            if base_query:
                print(f"   🔄 Retry without suffix: {base_query}")
                result = self._search_single(base_query, sleep_sec)
                if result:
                    return result

        return None

    def delete_playlist(self, playlist_id: str) -> bool:
        """
        プレイリストを削除

        Args:
            playlist_id: 削除するプレイリストのID

        Returns:
            成功した場合True
        """
        try:
            result = self.yt.delete_playlist(playlist_id)
            return result == "STATUS_SUCCEEDED" or isinstance(result, str)
        except Exception as e:
            print(f"Delete error: {e}")
            return False

    def create_playlist(
        self,
        title: str,
        description: str = "",
        video_ids: list[str] | None = None,
        privacy: str = "PRIVATE",
    ) -> str | None:
        """
        プレイリストを作成

        Args:
            title: プレイリストのタイトル
            description: プレイリストの説明
            video_ids: 追加するvideoIdのリスト
            privacy: 公開設定（PRIVATE, PUBLIC, UNLISTED）

        Returns:
            作成されたプレイリストのID（失敗時はNone）
        """
        try:
            result = self.yt.create_playlist(
                title=title,
                description=description,
                privacy_status=privacy,
                video_ids=video_ids,
            )
            if isinstance(result, str):
                return result
            return None
        except Exception as e:
            print(f"Create playlist error: {e}")
            return None

    def create_or_replace_playlist(
        self,
        playlist_name: str,
        song_data: list[tuple[str, bool]],
        description: str = "",
        privacy: str = "PRIVATE",
        verbose: bool = True,
    ) -> dict:
        """
        プレイリストをデリート・インサート（既存があれば削除して新規作成）

        Args:
            playlist_name: プレイリスト名
            song_data: [(video_id_or_query, is_video_id), ...]のリスト
                       is_video_id=Trueの場合、video_idを直接使用
                       is_video_id=Falseの場合、検索クエリとして検索
            description: プレイリストの説明
            privacy: 公開設定
            verbose: 詳細ログを出力するか

        Returns:
            {
                "playlist_id": str | None,
                "found_songs": list[dict],  # 見つかった曲
                "not_found": list[str],     # 見つからなかったクエリ
            }
        """
        result = {
            "playlist_id": None,
            "found_songs": [],
            "not_found": [],
        }

        # 1. 既存プレイリストを検索・削除
        existing_id = self.find_playlist_by_name(playlist_name)
        if existing_id:
            self.delete_playlist(existing_id)
            if verbose:
                print(f"🗑️  Deleted existing playlist: {playlist_name}")

        # 2. ビデオIDを取得（直接指定されたものと検索で取得したもの）
        video_ids = []
        for i, (data, is_video_id) in enumerate(song_data):
            if verbose:
                print(f"🔍 [{i + 1}/{len(song_data)}] Processing: {data}")

            if is_video_id:
                # ビデオIDが直接指定されている場合はそのまま使用
                # Note: API呼び出しを避けるため、メタデータは取得しない（プレースホルダー値を使用）
                video_ids.append(data)
                result["found_songs"].append(
                    {
                        "query": f"Video ID: {data}",
                        "videoId": data,
                        "title": "Direct video ID",  # プレースホルダー
                        "artist": "N/A",  # プレースホルダー
                    }
                )
                if verbose:
                    print(f"   ✅ Using video ID directly: {data}")
            else:
                # 検索クエリの場合は検索を実行
                song_info = self.search_video_id(data)
                if song_info and song_info.get("videoId"):
                    video_ids.append(song_info["videoId"])
                    result["found_songs"].append(
                        {
                            "query": data,
                            "videoId": song_info["videoId"],
                            "title": song_info["title"],
                            "artist": song_info["artist"],
                        }
                    )
                    if verbose:
                        print(f"   ✅ Found: {song_info['title']} - {song_info['artist']}")
                else:
                    result["not_found"].append(data)
                    if verbose:
                        print(f"   ❌ Not found")

        # 3. 新規プレイリスト作成
        if video_ids:
            playlist_id = self.create_playlist(
                title=playlist_name,
                description=description,
                video_ids=video_ids,
                privacy=privacy,
            )
            result["playlist_id"] = playlist_id

            if verbose:
                print(f"\n🎵 Created playlist: {playlist_name}")
                print(f"   Songs: {len(video_ids)} / {len(song_data)}")
                if playlist_id:
                    print(
                        f"   URL: https://music.youtube.com/playlist?list={playlist_id}"
                    )
        else:
            if verbose:
                print(f"\n⚠️  No songs found, playlist not created")

        return result


def setup_oauth(
    oauth_file: str = "oauth.json",
    secrets_file: str = "secrets.json",
):
    """
    OAuth認証をセットアップ（初回のみ実行）

    Args:
        oauth_file: 認証ファイルの出力先
        secrets_file: クライアントID/シークレットが含まれるJSONファイルのパス
    """
    from ytmusicapi import YTMusic, OAuthCredentials

    secrets = load_secrets(secrets_file)
    oauth_credentials = OAuthCredentials(
        client_id=secrets["client_id"],
        client_secret=secrets["client_secret"],
    )
    YTMusic.setup_oauth(
        filepath=oauth_file,
        open_browser=True,
        oauth_credentials=oauth_credentials,
    )
    print(f"✅ OAuth setup complete: {oauth_file}")
