"""
Moodle REST API connector — i3EduBridge (Moodle 4.4)
Publishes SCORM packages and EPUB books to Moodle courses via web services.

Prerequisites (one-time Moodle admin setup):
  1. Enable web services: Site admin → Advanced features → Enable web services
  2. Enable REST protocol: Site admin → Plugins → Web services → Manage protocols
  3. Create token: Site admin → Plugins → Web services → Manage tokens
     → Select user=i3admin, service=i3smartlab
  4. Create external service "i3smartlab" with these functions:
       core_course_create_courses
       core_course_get_courses
       mod_scorm_get_scorm_scos
       core_files_upload
       mod_resource_get_resource_by_id
"""

import os
import io
import json
import logging
import httpx
from typing import Optional

logger = logging.getLogger("smartlab.moodle")

MOODLE_URL      = os.environ["MOODLE_URL"]
MOODLE_EXT_URL  = os.environ["MOODLE_EXTERNAL_URL"]
MOODLE_WS_TOKEN = os.environ["MOODLE_WS_TOKEN"]

REST_URL = f"{MOODLE_URL}/webservice/rest/server.php"


async def _call(wsfunction: str, params: dict, timeout: int = 30) -> dict:
    """Call Moodle web service REST endpoint."""
    payload = {
        "wstoken": MOODLE_WS_TOKEN,
        "wsfunction": wsfunction,
        "moodlewsrestformat": "json",
        **params,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(REST_URL, data=payload)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "exception" in data:
            raise Exception(f"Moodle WS error [{wsfunction}]: {data.get('message', data)}")
        return data


async def get_or_create_course(
    shortname: str, fullname: str, category_id: int = 1,
    summary: str = "", visible: bool = True
) -> dict:
    """
    Get existing course by shortname or create a new one.
    Returns Moodle course dict with 'id'.
    """
    # Search for existing
    try:
        result = await _call("core_course_get_courses_by_field", {
            "field": "shortname",
            "value": shortname,
        })
        courses = result.get("courses", [])
        if courses:
            logger.info(f"Moodle course exists: {shortname} (id={courses[0]['id']})")
            return courses[0]
    except Exception as e:
        logger.warning(f"Could not search courses: {e}")

    # Create new
    result = await _call("core_course_create_courses", {
        "courses[0][shortname]":   shortname,
        "courses[0][fullname]":    fullname,
        "courses[0][categoryid]":  str(category_id),
        "courses[0][summary]":     summary,
        "courses[0][summaryformat]": "1",
        "courses[0][visible]":     "1" if visible else "0",
        "courses[0][format]":      "topics",
    })
    course = result[0]
    logger.info(f"Created Moodle course: {fullname} (id={course['id']})")
    return course


async def upload_scorm_package(
    course_id: int, section_id: int,
    scorm_zip_bytes: bytes, activity_name: str,
    scorm_version: str = "2004",
    mastery_score: int = 80,
    max_attempts: int = 3,
) -> dict:
    """
    Upload a SCORM ZIP to Moodle and create a SCORM activity.
    Returns the created activity info.
    """
    # Step 1: Upload file to Moodle draft area
    upload_url = f"{MOODLE_URL}/webservice/upload.php"
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            upload_url,
            params={"token": MOODLE_WS_TOKEN},
            files={"file": ("course.zip", scorm_zip_bytes, "application/zip")},
        )
        resp.raise_for_status()
        upload_info = resp.json()
        if isinstance(upload_info, list):
            upload_info = upload_info[0]
        itemid = upload_info.get("itemid")

    logger.info(f"Uploaded SCORM ZIP to Moodle draft area, itemid={itemid}")

    # Step 2: Create SCORM activity
    scorm_type = "scorm12" if scorm_version == "1.2" else "scorm2004"
    result = await _call("mod_scorm_add_instance", {
        "courseid":          str(course_id),
        "section":           str(section_id),
        "name":              activity_name,
        "scormtype":         "local",
        "packageitemid":     str(itemid),
        "packagefilepath":   "",
        "masteryoverride":   "1",
        "maxgrade":          "100",
        "grademethod":       "2",
        "maxattempt":        str(max_attempts),
        "forcecompleted":    "0",
        "forcenewattempt":   "0",
        "lastattemptlock":   "0",
        "displayattemptstatus": "1",
        "completionstatusrequired": "4",
        "completionscorerequired": str(mastery_score),
    }, timeout=60)

    logger.info(f"Created SCORM activity in course {course_id}: {activity_name}")
    return result


async def create_video_resource(
    course_id: int, section_id: int,
    video_url: str, title: str, description: str = ""
) -> dict:
    """Create a URL resource in Moodle pointing to HLS stream."""
    result = await _call("mod_url_add_instance", {
        "courseid":      str(course_id),
        "section":       str(section_id),
        "name":          title,
        "externalurl":   video_url,
        "intro":         description,
        "introformat":   "1",
        "display":       "6",   # open in new window
    }, timeout=30)
    logger.info(f"Created video resource in course {course_id}: {title}")
    return result


async def upload_epub_resource(
    course_id: int, section_id: int,
    epub_bytes: bytes, title: str, description: str = ""
) -> dict:
    """Upload an EPUB3 file as a file resource in Moodle."""
    upload_url = f"{MOODLE_URL}/webservice/upload.php"
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            upload_url,
            params={"token": MOODLE_WS_TOKEN},
            files={"file": (f"{title}.epub", epub_bytes, "application/epub+zip")},
        )
        resp.raise_for_status()
        upload_info = resp.json()
        if isinstance(upload_info, list):
            upload_info = upload_info[0]
        itemid = upload_info.get("itemid")

    result = await _call("mod_resource_add_instance", {
        "courseid":           str(course_id),
        "section":            str(section_id),
        "name":               title,
        "intro":              description,
        "introformat":        "1",
        "files_filemanager":  str(itemid),
        "display":            "0",
    }, timeout=30)
    logger.info(f"Created EPUB resource in course {course_id}: {title}")
    return result


async def get_course_url(course_id: int) -> str:
    """Return the public Moodle URL for a course."""
    return f"{MOODLE_EXT_URL}/course/view.php?id={course_id}"


async def enrol_user(user_id: int, course_id: int, role_id: int = 5):
    """Enrol a user in a Moodle course (role 5 = student)."""
    await _call("enrol_manual_enrol_users", {
        "enrolments[0][roleid]":   str(role_id),
        "enrolments[0][userid]":   str(user_id),
        "enrolments[0][courseid]": str(course_id),
    })
