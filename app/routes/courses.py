from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Course, Registration
from app.schemas import CourseCreate, CourseUpdate, CourseOut
from app.auth import require_admin

router = APIRouter(prefix="/api/v1/courses", tags=["Courses"])

# Reading courses stays public (the student page lists them); only writes are gated.
admin_only = [Depends(require_admin)]

@router.get("", response_model=List[CourseOut])
def get_courses(active_only: bool = False, db: Session = Depends(get_db)):
    query = db.query(Course)
    if active_only:
        query = query.filter(Course.is_active == True)
    courses = query.order_by(Course.id.desc()).all()
    for c in courses:
        db_regs = db.query(Registration).filter(Registration.course_id == c.id).count()
        c.registered_count = (c.initial_registered_count or 0) + db_regs
    return courses

@router.get("/{course_id}", response_model=CourseOut)
def get_course(course_id: int, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    db_regs = db.query(Registration).filter(Registration.course_id == course.id).count()
    course.registered_count = (course.initial_registered_count or 0) + db_regs
    return course

@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED, dependencies=admin_only)
def create_course(course_in: CourseCreate, db: Session = Depends(get_db)):
    db_course = Course(**course_in.dict())
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    db_course.registered_count = db_course.initial_registered_count or 0
    return db_course

@router.put("/{course_id}", response_model=CourseOut, dependencies=admin_only)
def update_course(course_id: int, course_in: CourseUpdate, db: Session = Depends(get_db)):
    db_course = db.query(Course).filter(Course.id == course_id).first()
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    update_data = course_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_course, field, value)
        
    db.commit()
    db.refresh(db_course)
    db_regs = db.query(Registration).filter(Registration.course_id == db_course.id).count()
    db_course.registered_count = (db_course.initial_registered_count or 0) + db_regs
    return db_course

@router.delete("/{course_id}", dependencies=admin_only)
def delete_course(course_id: int, db: Session = Depends(get_db)):
    db_course = db.query(Course).filter(Course.id == course_id).first()
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete(db_course)
    db.commit()
    return {"message": "Course deleted successfully", "course_id": course_id}
