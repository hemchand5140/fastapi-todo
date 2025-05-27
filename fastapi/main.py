from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from sqlmodel import Field, SQLModel, Session, create_engine, select
from cachetools import TTLCache
import logging

# --------------------- Logging Setup ---------------------
logging.basicConfig(level=logging.INFO)

# --------------------- App Init ---------------------
app = FastAPI()

# --------------------- Student Model ---------------------
class Student(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    age: int
    grade: str

# --------------------- Database Setup ---------------------
sqlite_file_name = "students.db"
engine = create_engine(f"sqlite:///{sqlite_file_name}", echo=False)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# --------------------- Caching ---------------------
cache = TTLCache(maxsize=100, ttl=30)

# --------------------- HATEOAS + Caching + Async ---------------------
@app.get("/students")
async def get_students(version: str = Header(default="v1")):
    logging.info("Fetching students list")

    if 'students' in cache:
        logging.info("Serving from cache")
        return cache['students']

    with Session(engine) as session:
        statement = select(Student)
        results = session.exec(statement).all()

        students_with_links = []
        for student in results:
            students_with_links.append({
                "id": student.id,
                "name": student.name,
                "age": student.age,
                "grade": student.grade,
                "links": [
                    {"rel": "self", "href": f"/students/{student.id}"},
                    {"rel": "update", "href": f"/students/{student.id}"},
                    {"rel": "delete", "href": f"/students/{student.id}"}
                ]
            })
        cache['students'] = students_with_links
        return students_with_links

# --------------------- Add Student (Idempotency) ---------------------
@app.post("/students")
def add_student(student: Student):
    with Session(engine) as session:
        existing = session.exec(select(Student).where(Student.id == student.id)).first()
        if existing:
            raise HTTPException(status_code=409, detail="Student with this ID already exists")

        session.add(student)
        session.commit()
        session.refresh(student)
        return student

# --------------------- Webhook Receiver ---------------------
@app.post("/webhook")
def webhook_receiver(data: dict):
    logging.info(f"Webhook received: {data}")
    return {"status": "received", "data": data}

# --------------------- Versioning URI Based ---------------------
@app.get("/v1/students")
def v1_students():
    return {"version": "v1", "message": "Using v1 structure"}

@app.get("/v2/students")
def v2_students():
    return {"version": "v2", "message": "Using v2 structure with new features"}

# --------------------- Deprecated Endpoint ---------------------
@app.get("/students-deprecated")
def deprecated_students():
    return JSONResponse(
        content={"message": "This endpoint is deprecated. Please use /students"},
        headers={"Deprecation": "true"}
    )

# --------------------- Get Single Student ---------------------
@app.get("/students/{student_id}")
def get_student(student_id: int):
    with Session(engine) as session:
        student = session.get(Student, student_id)
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        return student

# --------------------- Update Student ---------------------
@app.put("/students/{student_id}")
def update_student(student_id: int, updated_data: Student):
    with Session(engine) as session:
        student = session.get(Student, student_id)
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        student.name = updated_data.name
        student.age = updated_data.age
        student.grade = updated_data.grade
        session.add(student)
        session.commit()
        session.refresh(student)
        return student

# --------------------- Delete Student ---------------------
@app.delete("/students/{student_id}")
def delete_student(student_id: int):
    with Session(engine) as session:
        student = session.get(Student, student_id)
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        session.delete(student)
        session.commit()
        return {"message": f"Student {student_id} deleted"}
