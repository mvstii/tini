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
    ForeignKey,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
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
    name_norm: Mapped[str | None] = mapped_column(String(256), index=True)


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
