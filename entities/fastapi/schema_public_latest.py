from __future__ import annotations
from pydantic import BaseModel
from pydantic import Field
from pydantic import UUID4
from pydantic.types import StringConstraints
from typing import Any
import datetime


# CUSTOM CLASSES
# Note: These are custom model classes for defining common features among
# Pydantic Base Schema.


class CustomModel(BaseModel):
	"""Base model class with common features."""
	pass


class CustomModelInsert(CustomModel):
	"""Base model for insert operations with common features."""
	pass


class CustomModelUpdate(CustomModel):
	"""Base model for update operations with common features."""
	pass


# BASE CLASSES
# Note: These are the base Row models that include all fields.


class CoursesBaseSchema(CustomModel):
	"""Courses Base Schema."""

	# Primary Keys
	id: UUID4

	# Columns
	created_at: datetime.datetime
	title: str | None = Field(default=None)


class SourcesBaseSchema(CustomModel):
	"""Sources Base Schema."""

	# Primary Keys
	id: int

	# Columns
	created_at: datetime.datetime


class UserCoursesBaseSchema(CustomModel):
	"""UserCourses Base Schema."""

	# Primary Keys
	id: UUID4

	# Columns
	course_id: UUID4
	created_at: datetime.datetime
	user_id: UUID4


class UsersBaseSchema(CustomModel):
	"""Users Base Schema."""

	# Primary Keys
	id: UUID4

	# Columns
	auth_id: UUID4 | None = Field(default=None)
	avatar_url: str | None = Field(default=None)
	created_at: datetime.datetime
	email: str | None = Field(default=None)
	full_name: str | None = Field(default=None)
	updated_at: datetime.datetime | None = Field(default=None)
# INSERT CLASSES
# Note: These models are used for insert operations. Auto-generated fields
# (like IDs and timestamps) are optional.


class CoursesInsert(CustomModelInsert):
	"""Courses Insert Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)  # has default value

	# Field properties:
	# created_at: has default value
	# title: nullable
	
		# Optional fields
	created_at: datetime.datetime | None = Field(default=None)
	title: str | None = Field(default=None)


class SourcesInsert(CustomModelInsert):
	"""Sources Insert Schema."""

	# Primary Keys
	

	# Field properties:
	# created_at: has default value
	
		# Optional fields
	created_at: datetime.datetime | None = Field(default=None)


class UserCoursesInsert(CustomModelInsert):
	"""UserCourses Insert Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)  # has default value

	# Field properties:
	# created_at: has default value
	
	# Required fields
	course_id: UUID4
	user_id: UUID4
	
		# Optional fields
	created_at: datetime.datetime | None = Field(default=None)


class UsersInsert(CustomModelInsert):
	"""Users Insert Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)  # has default value

	# Field properties:
	# auth_id: nullable, has default value
	# avatar_url: nullable
	# created_at: has default value
	# email: nullable
	# full_name: nullable
	# updated_at: nullable, has default value
	
		# Optional fields
	auth_id: UUID4 | None = Field(default=None)
	avatar_url: str | None = Field(default=None)
	created_at: datetime.datetime | None = Field(default=None)
	email: str | None = Field(default=None)
	full_name: str | None = Field(default=None)
	updated_at: datetime.datetime | None = Field(default=None)
# UPDATE CLASSES
# Note: These models are used for update operations. All fields are optional.


class CoursesUpdate(CustomModelUpdate):
	"""Courses Update Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)

	# Field properties:
	# created_at: has default value
	# title: nullable
	
		# Optional fields
	created_at: datetime.datetime | None = Field(default=None)
	title: str | None = Field(default=None)


class SourcesUpdate(CustomModelUpdate):
	"""Sources Update Schema."""

	# Primary Keys
	

	# Field properties:
	# created_at: has default value
	
		# Optional fields
	created_at: datetime.datetime | None = Field(default=None)


class UserCoursesUpdate(CustomModelUpdate):
	"""UserCourses Update Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)

	# Field properties:
	# created_at: has default value
	
		# Optional fields
	course_id: UUID4 | None = Field(default=None)
	created_at: datetime.datetime | None = Field(default=None)
	user_id: UUID4 | None = Field(default=None)


class UsersUpdate(CustomModelUpdate):
	"""Users Update Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)

	# Field properties:
	# auth_id: nullable, has default value
	# avatar_url: nullable
	# created_at: has default value
	# email: nullable
	# full_name: nullable
	# updated_at: nullable, has default value
	
		# Optional fields
	auth_id: UUID4 | None = Field(default=None)
	avatar_url: str | None = Field(default=None)
	created_at: datetime.datetime | None = Field(default=None)
	email: str | None = Field(default=None)
	full_name: str | None = Field(default=None)
	updated_at: datetime.datetime | None = Field(default=None)


# OPERATIONAL CLASSES


class Courses(CoursesBaseSchema):
	"""Courses Schema for Pydantic.

	Inherits from CoursesBaseSchema. Add any customization here.
	"""

	# Foreign Keys
	user_courses: list[UserCourses] | None = Field(default=None)


class Sources(SourcesBaseSchema):
	"""Sources Schema for Pydantic.

	Inherits from SourcesBaseSchema. Add any customization here.
	"""
	pass


class UserCourses(UserCoursesBaseSchema):
	"""UserCourses Schema for Pydantic.

	Inherits from UserCoursesBaseSchema. Add any customization here.
	"""

	# Foreign Keys
	courses: Courses | None = Field(default=None)
	users: Users | None = Field(default=None)


class Users(UsersBaseSchema):
	"""Users Schema for Pydantic.

	Inherits from UsersBaseSchema. Add any customization here.
	"""

	# Foreign Keys
	user_courses: list[UserCourses] | None = Field(default=None)
