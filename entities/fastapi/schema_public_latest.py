from __future__ import annotations
from pydantic import BaseModel
from pydantic import Field
from pydantic import Json
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


class AssignmentsBaseSchema(CustomModel):
	"""Assignments Base Schema."""

	# Primary Keys
	id: UUID4

	# Columns
	chosen_due_date_id: UUID4 | None = Field(default=None)
	content_hash: str | None = Field(default=None)
	course_id: UUID4 | None = Field(default=None)
	created_at: datetime.datetime
	description: str | None = Field(default=None)
	job_sync_id: UUID4 | None = Field(default=None)
	source_page_paths: list[Any] | None = Field(default=None)
	title: str | None = Field(default=None)


class CoursesBaseSchema(CustomModel):
	"""Courses Base Schema."""

	# Primary Keys
	id: UUID4

	# Columns
	created_at: datetime.datetime
	title: str | None = Field(default=None)


class DueDatesBaseSchema(CustomModel):
	"""DueDates Base Schema."""

	# Primary Keys
	id: UUID4

	# Columns
	assignment_id: UUID4 | None = Field(default=None)
	created_at: datetime.datetime
	date: datetime.datetime | None = Field(default=None)
	date_certain: bool | None = Field(default=None)
	description: str | None = Field(default=None)
	time_certain: bool | None = Field(default=None)
	title: str | None = Field(default=None)
	url: str | None = Field(default=None)


class JobSyncGroupsBaseSchema(CustomModel):
	"""JobSyncGroups Base Schema."""

	# Primary Keys
	id: UUID4

	# Columns
	completed_at: datetime.datetime | None = Field(default=None)
	created_at: datetime.datetime
	user_id: UUID4 | None = Field(default=None)


class JobSyncsBaseSchema(CustomModel):
	"""JobSyncs Base Schema."""

	# Primary Keys
	id: UUID4

	# Columns
	course_id: UUID4 | None = Field(default=None)
	created_at: datetime.datetime
	job_sync_group_id: UUID4 | None = Field(default=None)
	scraped_tree: dict | Json | None = Field(default=None)
	source_id: UUID4 | None = Field(default=None)


class SourcesBaseSchema(CustomModel):
	"""Sources Base Schema."""

	# Primary Keys
	id: UUID4

	# Columns
	course_id: UUID4 | None = Field(default=None)
	created_at: datetime.datetime
	needs_authentication: bool
	source_instructions: str | None = Field(default=None)
	url: str | None = Field(default=None)


class UserAssignmentsBaseSchema(CustomModel):
	"""UserAssignments Base Schema."""

	# Primary Keys
	id: UUID4

	# Columns
	assignment_id: UUID4 | None = Field(default=None)
	chosen_due_date_id: UUID4 | None = Field(default=None)
	completed_at: datetime.datetime | None = Field(default=None)
	created_at: datetime.datetime
	user_id: UUID4 | None = Field(default=None)


class UserAuthDetailsBaseSchema(CustomModel):
	"""UserAuthDetails Base Schema."""

	# Primary Keys
	id: UUID4

	# Columns
	cookies: dict | Json | None = Field(default=None)
	cookies_type: str | None = Field(default=None)
	created_at: datetime.datetime
	in_sync: bool | None = Field(default=None)
	user_id: UUID4 | None = Field(default=None)


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


class AssignmentsInsert(CustomModelInsert):
	"""Assignments Insert Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)  # has default value

	# Field properties:
	# chosen_due_date_id: nullable
	# content_hash: nullable
	# course_id: nullable
	# created_at: has default value
	# description: nullable
	# job_sync_id: nullable
	# source_page_paths: nullable, has default value
	# title: nullable
	
		# Optional fields
	chosen_due_date_id: UUID4 | None = Field(default=None)
	content_hash: str | None = Field(default=None)
	course_id: UUID4 | None = Field(default=None)
	created_at: datetime.datetime | None = Field(default=None)
	description: str | None = Field(default=None)
	job_sync_id: UUID4 | None = Field(default=None)
	source_page_paths: list[Any] | None = Field(default=None)
	title: str | None = Field(default=None)


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


class DueDatesInsert(CustomModelInsert):
	"""DueDates Insert Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)  # has default value

	# Field properties:
	# assignment_id: nullable
	# created_at: has default value
	# date: nullable
	# date_certain: nullable
	# description: nullable
	# time_certain: nullable
	# title: nullable
	# url: nullable
	
		# Optional fields
	assignment_id: UUID4 | None = Field(default=None)
	created_at: datetime.datetime | None = Field(default=None)
	date: datetime.datetime | None = Field(default=None)
	date_certain: bool | None = Field(default=None)
	description: str | None = Field(default=None)
	time_certain: bool | None = Field(default=None)
	title: str | None = Field(default=None)
	url: str | None = Field(default=None)


class JobSyncGroupsInsert(CustomModelInsert):
	"""JobSyncGroups Insert Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)  # has default value

	# Field properties:
	# completed_at: nullable
	# created_at: has default value
	# user_id: nullable
	
		# Optional fields
	completed_at: datetime.datetime | None = Field(default=None)
	created_at: datetime.datetime | None = Field(default=None)
	user_id: UUID4 | None = Field(default=None)


class JobSyncsInsert(CustomModelInsert):
	"""JobSyncs Insert Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)  # has default value

	# Field properties:
	# course_id: nullable
	# created_at: has default value
	# job_sync_group_id: nullable
	# scraped_tree: nullable
	# source_id: nullable
	
		# Optional fields
	course_id: UUID4 | None = Field(default=None)
	created_at: datetime.datetime | None = Field(default=None)
	job_sync_group_id: UUID4 | None = Field(default=None)
	scraped_tree: dict | Json | None = Field(default=None)
	source_id: UUID4 | None = Field(default=None)


class SourcesInsert(CustomModelInsert):
	"""Sources Insert Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)  # has default value

	# Field properties:
	# course_id: nullable
	# created_at: has default value
	# needs_authentication: has default value
	# source_instructions: nullable
	# url: nullable
	
		# Optional fields
	course_id: UUID4 | None = Field(default=None)
	created_at: datetime.datetime | None = Field(default=None)
	needs_authentication: bool | None = Field(default=None)
	source_instructions: str | None = Field(default=None)
	url: str | None = Field(default=None)


class UserAssignmentsInsert(CustomModelInsert):
	"""UserAssignments Insert Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)  # has default value

	# Field properties:
	# assignment_id: nullable
	# chosen_due_date_id: nullable
	# completed_at: nullable
	# created_at: has default value
	# user_id: nullable
	
		# Optional fields
	assignment_id: UUID4 | None = Field(default=None)
	chosen_due_date_id: UUID4 | None = Field(default=None)
	completed_at: datetime.datetime | None = Field(default=None)
	created_at: datetime.datetime | None = Field(default=None)
	user_id: UUID4 | None = Field(default=None)


class UserAuthDetailsInsert(CustomModelInsert):
	"""UserAuthDetails Insert Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)  # has default value

	# Field properties:
	# cookies: nullable
	# cookies_type: nullable
	# created_at: has default value
	# in_sync: nullable
	# user_id: nullable
	
		# Optional fields
	cookies: dict | Json | None = Field(default=None)
	cookies_type: str | None = Field(default=None)
	created_at: datetime.datetime | None = Field(default=None)
	in_sync: bool | None = Field(default=None)
	user_id: UUID4 | None = Field(default=None)


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


class AssignmentsUpdate(CustomModelUpdate):
	"""Assignments Update Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)

	# Field properties:
	# chosen_due_date_id: nullable
	# content_hash: nullable
	# course_id: nullable
	# created_at: has default value
	# description: nullable
	# job_sync_id: nullable
	# source_page_paths: nullable, has default value
	# title: nullable
	
		# Optional fields
	chosen_due_date_id: UUID4 | None = Field(default=None)
	content_hash: str | None = Field(default=None)
	course_id: UUID4 | None = Field(default=None)
	created_at: datetime.datetime | None = Field(default=None)
	description: str | None = Field(default=None)
	job_sync_id: UUID4 | None = Field(default=None)
	source_page_paths: list[Any] | None = Field(default=None)
	title: str | None = Field(default=None)


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


class DueDatesUpdate(CustomModelUpdate):
	"""DueDates Update Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)

	# Field properties:
	# assignment_id: nullable
	# created_at: has default value
	# date: nullable
	# date_certain: nullable
	# description: nullable
	# time_certain: nullable
	# title: nullable
	# url: nullable
	
		# Optional fields
	assignment_id: UUID4 | None = Field(default=None)
	created_at: datetime.datetime | None = Field(default=None)
	date: datetime.datetime | None = Field(default=None)
	date_certain: bool | None = Field(default=None)
	description: str | None = Field(default=None)
	time_certain: bool | None = Field(default=None)
	title: str | None = Field(default=None)
	url: str | None = Field(default=None)


class JobSyncGroupsUpdate(CustomModelUpdate):
	"""JobSyncGroups Update Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)

	# Field properties:
	# completed_at: nullable
	# created_at: has default value
	# user_id: nullable
	
		# Optional fields
	completed_at: datetime.datetime | None = Field(default=None)
	created_at: datetime.datetime | None = Field(default=None)
	user_id: UUID4 | None = Field(default=None)


class JobSyncsUpdate(CustomModelUpdate):
	"""JobSyncs Update Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)

	# Field properties:
	# course_id: nullable
	# created_at: has default value
	# job_sync_group_id: nullable
	# scraped_tree: nullable
	# source_id: nullable
	
		# Optional fields
	course_id: UUID4 | None = Field(default=None)
	created_at: datetime.datetime | None = Field(default=None)
	job_sync_group_id: UUID4 | None = Field(default=None)
	scraped_tree: dict | Json | None = Field(default=None)
	source_id: UUID4 | None = Field(default=None)


class SourcesUpdate(CustomModelUpdate):
	"""Sources Update Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)

	# Field properties:
	# course_id: nullable
	# created_at: has default value
	# needs_authentication: has default value
	# source_instructions: nullable
	# url: nullable
	
		# Optional fields
	course_id: UUID4 | None = Field(default=None)
	created_at: datetime.datetime | None = Field(default=None)
	needs_authentication: bool | None = Field(default=None)
	source_instructions: str | None = Field(default=None)
	url: str | None = Field(default=None)


class UserAssignmentsUpdate(CustomModelUpdate):
	"""UserAssignments Update Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)

	# Field properties:
	# assignment_id: nullable
	# chosen_due_date_id: nullable
	# completed_at: nullable
	# created_at: has default value
	# user_id: nullable
	
		# Optional fields
	assignment_id: UUID4 | None = Field(default=None)
	chosen_due_date_id: UUID4 | None = Field(default=None)
	completed_at: datetime.datetime | None = Field(default=None)
	created_at: datetime.datetime | None = Field(default=None)
	user_id: UUID4 | None = Field(default=None)


class UserAuthDetailsUpdate(CustomModelUpdate):
	"""UserAuthDetails Update Schema."""

	# Primary Keys
	id: UUID4 | None = Field(default=None)

	# Field properties:
	# cookies: nullable
	# cookies_type: nullable
	# created_at: has default value
	# in_sync: nullable
	# user_id: nullable
	
		# Optional fields
	cookies: dict | Json | None = Field(default=None)
	cookies_type: str | None = Field(default=None)
	created_at: datetime.datetime | None = Field(default=None)
	in_sync: bool | None = Field(default=None)
	user_id: UUID4 | None = Field(default=None)


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


class Assignments(AssignmentsBaseSchema):
	"""Assignments Schema for Pydantic.

	Inherits from AssignmentsBaseSchema. Add any customization here.
	"""

	# Foreign Keys
	courses: Courses | None = Field(default=None)
	job_syncs: JobSyncs | None = Field(default=None)
	due_dates: DueDates | None = Field(default=None)
	user_assignments: list[UserAssignments] | None = Field(default=None)


class Courses(CoursesBaseSchema):
	"""Courses Schema for Pydantic.

	Inherits from CoursesBaseSchema. Add any customization here.
	"""

	# Foreign Keys
	assignments: list[Assignments] | None = Field(default=None)
	job_syncs: list[JobSyncs] | None = Field(default=None)
	sources: list[Sources] | None = Field(default=None)
	user_courses: list[UserCourses] | None = Field(default=None)


class DueDates(DueDatesBaseSchema):
	"""DueDates Schema for Pydantic.

	Inherits from DueDatesBaseSchema. Add any customization here.
	"""

	# Foreign Keys
	assignments: Assignments | None = Field(default=None)
	user_assignments: list[UserAssignments] | None = Field(default=None)


class JobSyncGroups(JobSyncGroupsBaseSchema):
	"""JobSyncGroups Schema for Pydantic.

	Inherits from JobSyncGroupsBaseSchema. Add any customization here.
	"""

	# Foreign Keys
	users: Users | None = Field(default=None)
	job_syncs: list[JobSyncs] | None = Field(default=None)


class JobSyncs(JobSyncsBaseSchema):
	"""JobSyncs Schema for Pydantic.

	Inherits from JobSyncsBaseSchema. Add any customization here.
	"""

	# Foreign Keys
	job_sync_groups: JobSyncGroups | None = Field(default=None)
	sources: Sources | None = Field(default=None)
	courses: Courses | None = Field(default=None)
	assignments: list[Assignments] | None = Field(default=None)


class Sources(SourcesBaseSchema):
	"""Sources Schema for Pydantic.

	Inherits from SourcesBaseSchema. Add any customization here.
	"""

	# Foreign Keys
	courses: Courses | None = Field(default=None)
	job_syncs: list[JobSyncs] | None = Field(default=None)


class UserAssignments(UserAssignmentsBaseSchema):
	"""UserAssignments Schema for Pydantic.

	Inherits from UserAssignmentsBaseSchema. Add any customization here.
	"""

	# Foreign Keys
	due_dates: DueDates | None = Field(default=None)
	users: Users | None = Field(default=None)
	assignments: Assignments | None = Field(default=None)


class UserAuthDetails(UserAuthDetailsBaseSchema):
	"""UserAuthDetails Schema for Pydantic.

	Inherits from UserAuthDetailsBaseSchema. Add any customization here.
	"""

	# Foreign Keys
	users: Users | None = Field(default=None)


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
	job_sync_groups: list[JobSyncGroups] | None = Field(default=None)
	user_assignments: list[UserAssignments] | None = Field(default=None)
	user_auth_details: list[UserAuthDetails] | None = Field(default=None)
	user_courses: list[UserCourses] | None = Field(default=None)
