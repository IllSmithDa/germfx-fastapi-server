# tests/test_auth.py
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException
from jose import jwt

from app.core.auth import (
    create_access_token,
    create_refresh_token,
    verify_token,
    verify_user,
    get_authenticated_user,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.models import User


class TestCreateAccessToken:
    """Test suite for create_access_token function"""

    def test_should_create_valid_access_token_with_correct_payload_structure(self):
        """Should create a valid access token with correct payload structure"""
        # Arrange
        data = {"sub": "123", "username": "testuser"}
        
        # Act
        token = create_access_token(data)
        
        # Assert
        assert token is not None
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "123"
        assert payload["username"] == "testuser"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_should_respect_custom_expiration_delta(self):
        """Should create token with custom expiration time when provided"""
        # Arrange
        data = {"sub": "123"}
        custom_delta = timedelta(minutes=60)
        
        # Act
        token = create_access_token(data, expires_delta=custom_delta)
        
        # Assert
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat_time = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        delta = exp_time - iat_time
        
        # Allow 1 second tolerance for execution time
        assert abs(delta.total_seconds() - 3600) < 1

    def test_should_use_default_expiration_when_none_provided(self):
        """Should use default ACCESS_TOKEN_EXPIRE_MINUTES when no delta provided"""
        # Arrange
        data = {"sub": "123"}
        
        # Act
        token = create_access_token(data)
        
        # Assert
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat_time = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        delta = exp_time - iat_time
        
        expected_seconds = ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert abs(delta.total_seconds() - expected_seconds) < 1


class TestCreateRefreshToken:
    """Test suite for create_refresh_token function"""

    def test_should_create_valid_refresh_token_with_correct_payload_structure(self):
        """Should create a valid refresh token with correct payload structure"""
        # Arrange
        data = {"sub": "456", "username": "refreshuser"}
        
        # Act
        token = create_refresh_token(data)
        
        # Assert
        assert token is not None
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "456"
        assert payload["username"] == "refreshuser"
        assert payload["type"] == "refresh"
        assert "exp" in payload
        assert "iat" in payload

    def test_should_use_refresh_token_expiration_days(self):
        """Should create refresh token with REFRESH_TOKEN_EXPIRE_DAYS expiration"""
        # Arrange
        data = {"sub": "456"}
        
        # Act
        token = create_refresh_token(data)
        
        # Assert
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat_time = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        delta = exp_time - iat_time
        
        expected_seconds = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        assert abs(delta.total_seconds() - expected_seconds) < 1


class TestVerifyToken:
    """Test suite for verify_token function"""

    def test_should_verify_valid_access_token_and_return_payload(self):
        """Should verify a valid access token and return payload"""
        # Arrange
        data = {"sub": "789", "username": "verifyuser"}
        token = create_access_token(data)
        
        # Act
        payload = verify_token(token, token_type="access")
        
        # Assert
        assert payload["sub"] == "789"
        assert payload["username"] == "verifyuser"
        assert payload["type"] == "access"

    def test_should_reject_refresh_token_when_access_token_expected(self):
        """Should reject a refresh token when access token is expected"""
        # Arrange
        data = {"sub": "789"}
        refresh_token = create_refresh_token(data)
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            verify_token(refresh_token, token_type="access")
        
        assert exc_info.value.status_code == 401
        assert "Invalid token type" in exc_info.value.detail

    def test_should_reject_access_token_when_refresh_token_expected(self):
        """Should reject an access token when refresh token is expected"""
        # Arrange
        data = {"sub": "789"}
        access_token = create_access_token(data)
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            verify_token(access_token, token_type="refresh")
        
        assert exc_info.value.status_code == 401
        assert "Invalid token type" in exc_info.value.detail

    def test_should_raise_http_exception_for_expired_token(self):
        """Should raise HTTPException for expired tokens"""
        # Arrange
        data = {"sub": "789"}
        expired_delta = timedelta(seconds=-10)  # Already expired
        expired_token = create_access_token(data, expires_delta=expired_delta)
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            verify_token(expired_token, token_type="access")
        
        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in exc_info.value.detail

    def test_should_raise_http_exception_for_invalid_token(self):
        """Should raise HTTPException for malformed or invalid tokens"""
        # Arrange
        invalid_token = "this.is.not.a.valid.jwt.token"
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            verify_token(invalid_token, token_type="access")
        
        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in exc_info.value.detail


class TestVerifyUser:
    """Test suite for verify_user function"""

    @patch("app.core.auth.hash_email")
    @patch("app.util.security.verify_password")
    def test_should_verify_user_by_email_with_correct_password(
        self, mock_verify_password, mock_hash_email
    ):
        """Should verify user by email with correct password"""
        # Arrange
        mock_db = Mock()
        mock_user = User(
            id=1,
            username="testuser",
            email_hash="hashed_email",
            password_hash="hashed_password"
        )
        
        mock_hash_email.return_value = "hashed_email"
        mock_verify_password.return_value = True
        
        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        # Act
        user = verify_user("test@example.com", "correct_password", mock_db)
        
        # Assert
        assert user == mock_user
        mock_hash_email.assert_called_once_with("test@example.com")
        mock_verify_password.assert_called_once_with("correct_password", "hashed_password")

    @patch("app.util.security.verify_password")
    def test_should_verify_user_by_username_with_correct_password(
        self, mock_verify_password
    ):
        """Should verify user by username with correct password"""
        # Arrange
        mock_db = Mock()
        mock_user = User(
            id=2,
            username="testuser",
            email_hash="hashed_email",
            password_hash="hashed_password"
        )
        
        mock_verify_password.return_value = True
        
        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        # Act
        user = verify_user("testuser", "correct_password", mock_db)
        
        # Assert
        assert user == mock_user
        mock_verify_password.assert_called_once_with("correct_password", "hashed_password")

    @patch("app.util.security.verify_password")
    def test_should_raise_http_exception_for_invalid_credentials_wrong_password(
        self, mock_verify_password
    ):
        """Should raise HTTPException for invalid credentials (wrong password)"""
        # Arrange
        mock_db = Mock()
        mock_user = User(
            id=3,
            username="testuser",
            email_hash="hashed_email",
            password_hash="hashed_password"
        )
        
        mock_verify_password.return_value = False
        
        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            verify_user("testuser", "wrong_password", mock_db)
        
        assert exc_info.value.status_code == 401
        assert "Invalid credentials" in exc_info.value.detail

    def test_should_raise_http_exception_for_non_existent_user(self):
        """Should raise HTTPException for non-existent user"""
        # Arrange
        mock_db = Mock()
        
        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            verify_user("nonexistent", "password", mock_db)
        
        assert exc_info.value.status_code == 401
        assert "Invalid credentials" in exc_info.value.detail


class TestGetAuthenticatedUser:
    """Test suite for get_authenticated_user function"""

    @patch("app.core.auth.verify_token")
    def test_should_return_user_for_valid_access_token(self, mock_verify_token):
        """Should return authenticated user for valid access token"""
        # Arrange
        mock_db = Mock()
        mock_user = User(
            id=10,
            username="authuser",
            email_hash="hashed",
            password_hash="hashed"
        )
        
        mock_verify_token.return_value = {"sub": "10", "type": "access"}
        mock_db.get.return_value = mock_user
        
        # Act
        user = get_authenticated_user(access_token="valid_token", db=mock_db)
        
        # Assert
        assert user == mock_user
        mock_verify_token.assert_called_once_with("valid_token", token_type="access")
        mock_db.get.assert_called_once_with(User, 10)

    def test_should_raise_http_exception_when_no_token_provided(self):
        """Should raise HTTPException when no access token is provided"""
        # Arrange
        mock_db = Mock()
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_authenticated_user(access_token=None, db=mock_db)
        
        assert exc_info.value.status_code == 401
        assert "Not authenticated" in exc_info.value.detail

    @patch("app.core.auth.verify_token")
    def test_should_raise_http_exception_when_token_missing_sub(self, mock_verify_token):
        """Should raise HTTPException when token payload is missing 'sub' field"""
        # Arrange
        mock_db = Mock()
        mock_verify_token.return_value = {"type": "access"}  # Missing 'sub'
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_authenticated_user(access_token="token_without_sub", db=mock_db)
        
        assert exc_info.value.status_code == 401
        assert "Invalid token" in exc_info.value.detail

    @patch("app.core.auth.verify_token")
    def test_should_raise_http_exception_when_user_not_found_in_db(self, mock_verify_token):
        """Should raise HTTPException when user ID from token doesn't exist in database"""
        # Arrange
        mock_db = Mock()
        mock_verify_token.return_value = {"sub": "999", "type": "access"}
        mock_db.get.return_value = None  # User not found
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_authenticated_user(access_token="valid_token", db=mock_db)
        
        assert exc_info.value.status_code == 401
        assert "User not found" in exc_info.value.detail
