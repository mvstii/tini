"""Veri modeli.

Kişisel veri (user, service_connection, user_track_link, user_track_meta, vote_event):
user_id FK'leri ON DELETE CASCADE; hesap silinince hepsi gider.
Paylaşılan katalog (artist, track): kişisel veri ve Spotify metadata'sı içermez; yalnızca
ISRC/MBID ve kendi türettiğimiz veri.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

_now = func.now()


class User(Base):
    __tablename__ = "user_account"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now)


class ServiceConnection(Base):
    """Kullanıcının bağladığı müzik servisi. Token'lar Fernet ile şifreli."""

    __tablename__ = "service_connection"
    __table_args__ = (UniqueConstraint("user_id", "service"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    service: Mapped[str] = mapped_column(String(32))
    external_user_id: Mapped[str] = mapped_column(String(128))
    access_token_enc: Mapped[bytes] = mapped_column(LargeBinary)
    refresh_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now)


class Artist(Base):
    """Paylaşılan katalog. Ad MusicBrainz/Last.fm'den gelir, Spotify'dan değil."""

    __tablename__ = "artist"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mbid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)
    name: Mapped[str | None] = mapped_column(Text)  # kanonik ad (MusicBrainz/Last.fm)
    name_norm: Mapped[str | None] = mapped_column(String(256), index=True)


class ArtistRef(Base):
    """Paylaşılan: sanatçının sağlayıcıdaki kimliği (ör. musicbrainz/<mbid>)."""

    __tablename__ = "artist_ref"
    __table_args__ = (UniqueConstraint("provider", "provider_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artist.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    provider_id: Mapped[str] = mapped_column(String(128))
    match_method: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)


class UserTrackArtist(Base):
    """Kullanıcıya özel: "bu şarkı bu sanatçıdır" bağı (kademe B). Kullanıcı silinince gider."""

    __tablename__ = "user_track_artist"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), primary_key=True
    )
    track_id: Mapped[int] = mapped_column(ForeignKey("track.id"), primary_key=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artist.id"), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(32))


class FetchLog(Base):
    """Paylaşılan negatif/pozitif önbellek: aynı anahtar için tekrar dış çağrıyı önler.

    key örn. "isrc:USRC17607839" veya "artist:123"; status: ok | empty | error.
    """

    __tablename__ = "fetch_log"

    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    status: Mapped[str] = mapped_column(String(16))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ArtistEdge(Base):
    """Paylaşılan benzerlik kenarı (yönlü, kaynak ham ağırlığı 0–1). Kişisel veri içermez."""

    __tablename__ = "artist_edge"

    src: Mapped[int] = mapped_column(ForeignKey("artist.id"), primary_key=True)
    dst: Mapped[int] = mapped_column(ForeignKey("artist.id"), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    weight: Mapped[float] = mapped_column(Float)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=_now, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GraphSnapshot(Base):
    """Paylaşılan: genişletme sonrası grafiğin sürümü (S4 matrisi bu sürümden kurulur)."""

    __tablename__ = "graph_snapshot"

    version: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now)
    edge_count: Mapped[int] = mapped_column(Integer)
    params: Mapped[dict] = mapped_column(JSONB)


class Track(Base):
    """Paylaşılan katalog. Kalıcı kimlik ISRC; başlık/sanatçı/süre burada tutulmaz."""

    __tablename__ = "track"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    isrc: Mapped[str] = mapped_column(String(12), unique=True)
    mbid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    artist_id: Mapped[int | None] = mapped_column(ForeignKey("artist.id"), index=True)


class UserTrackLink(Base):
    """Kimlik eşlemesi: kullanıcının servisindeki ID -> katalog parçası. Kullanıcıya özel."""

    __tablename__ = "user_track_link"
    __table_args__ = (UniqueConstraint("user_id", "service", "external_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    service: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(128))
    track_id: Mapped[int] = mapped_column(ForeignKey("track.id"), index=True)


class UserTrackMeta(Base):
    """Servis metadata'sı için kullanıcıya özel TTL önbelleği (süresi dolunca yenilenir)."""

    __tablename__ = "user_track_meta"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), primary_key=True
    )
    track_id: Mapped[int] = mapped_column(ForeignKey("track.id"), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    artist_names: Mapped[list[str]] = mapped_column(ARRAY(Text))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class VoteEvent(Base):
    """Silinmeyen olay kaydı. Güncel oy = parçanın son olayı. UPDATE veritabanında engellidir."""

    __tablename__ = "vote_event"
    __table_args__ = (CheckConstraint("vote BETWEEN 1 AND 6", name="vote_range"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    track_id: Mapped[int] = mapped_column(ForeignKey("track.id"), index=True)
    vote: Mapped[int] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now)


class TasteProfile(Base):
    """Kişisel, sürümlü profil anlık görüntüsü (oy olaylarından türetilir). Hesapla silinir."""

    __tablename__ = "taste_profile"
    __table_args__ = (UniqueConstraint("user_id", "version"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    algo_version: Mapped[str] = mapped_column(String(32))
    graph_version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now)
    body: Mapped[dict] = mapped_column(JSONB)


class UserSession(Base):
    """Oturum kaydı; veritabanında yalnızca SHA-256 özeti durur."""

    __tablename__ = "user_session"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OAuthState(Base):
    """Devam eden OAuth isteği (PKCE doğrulayıcısı); kısa ömürlü, kullanıcıya özel."""

    __tablename__ = "oauth_state"

    state: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    verifier: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
