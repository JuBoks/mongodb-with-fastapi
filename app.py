import os
from fastapi import FastAPI, Body, HTTPException, status
from fastapi.responses import Response, JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId
from typing import Optional, List
import motor.motor_asyncio

app = FastAPI()
client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGODB_URL"]) # motor driver를 통해 클라이언트 생성
db = client.college # college라는 db에 연결

"""
❓ PyObjectId(ObjectId)가 왜 필요한가요??

❗️ 요약
❗️ 해당 타입이 없으면 JSONResponse()에서 결과를 반환할 때, 결과에 ObjectId타입을 JSON형태로 변환할 수가 없음.
❗️ 따라서 애초에 _id값을 넣을 때 str형태로 넣는것임

⚠️ 상세설명
MongoDB에서 문서를 저장하고 검색하는 데 사용됩니다.

ObjectId는 MongoDB의 고유 식별자로 사용되는 데이터 형식입니다. 
ObjectId는 12바이트의 이진 데이터로 구성되며, 일반적으로 MongoDB 문서의 고유 식별자로 사용됩니다. 
그러나 ObjectId는 JSON에서 직접적으로 인코딩될 수 있는 데이터 형식이 아닙니다. 
JSON은 문자열, 숫자, 배열, 객체 등의 원시 데이터 형식을 지원하지만, ObjectId는 이러한 원시 데이터 형식에 포함되지 않습니다.

따라서, ObjectId를 JSON으로 직접 인코딩하려고 하면 문제가 발생하게 됩니다. 
이를 해결하기 위해서는 ObjectId를 JSON에서 처리할 수 있는 형식으로 변환해야 합니다. 
이를 위해 일반적으로 ObjectId를 문자열 형태로 변환하여 JSON으로 표현합니다. 
이렇게 하면 ObjectId를 JSON에서 사용할 수 있게 됩니다.
"""
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


class StudentModel(BaseModel):
    # default_factory=PyObjectId는 PyObjectId 클래스의 생성자를 기본값 팩토리로 지정하는 것을 의미합니다. 따라서, id 필드가 초기화될 때 기본적으로 PyObjectId의 인스턴스가 생성됩니다.
    # 별칭(alias)을 _(underscore) 형태로 줌으로써, private variable형태로 바꾸고, 이로 인해 외부에서 해당 필드에 대해 직접 수정할 수 없게 됨.
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    # Field(...) 같이 ellipse는 필드가 필수적이며 누락될 수 없음을 나타냅니다. 인스턴스를 생성할 때 name 필드의 값을 반드시 제공해야 합니다.
    name: str = Field(...)
    email: EmailStr = Field(...)
    course: str = Field(...)
    gpa: float = Field(..., le=4.0)

    class Config:
        # 모델의 필드에 대한 데이터를 필드 이름을 통해 직접 할당할 수 있게 됩니다.
        # 예를 들어, user = User(name="Alice", age=25) 이렇게만 사용해야만 했다면, 밑의 설정으로
        # user = User()  user.name = "Alice"  user.age = 25 같이 사용할 수 있음
        allow_population_by_field_name = True

        # 사용자가 정의한 클래스나 외부 라이브러리의 사용자 지정 타입을 Pydantic 모델에서 사용해야 할 때 arbitrary_types_allowed를 True로 설정하여 임의의 타입을 허용할 수 있습니다. 
        arbitrary_types_allowed = True

        # json_encoders 설정을 사용하여 ObjectId를 문자열로 인코딩하는 방법을 지정함. 
        # FastAPI는 JSON으로 직렬화할 때 ObjectId를 문자열로 변환하여 처리합니다. 이렇게 함으로써 ObjectId를 JSON에서 사용할 수 있게 됩니다.
        json_encoders = {ObjectId: str} 

        schema_extra = {
            "example": {
                "name": "Jane Doe",
                "email": "jdoe@example.com",
                "course": "Experiments, Science, and Fashion in Nanophotonics",
                "gpa": "3.0",
            }
        }


class UpdateStudentModel(BaseModel):
    # Optional은 Pydantic에서 사용되는 타입 힌트로, 필드가 선택적임을 나타냅니다. 즉, 해당 필드가 값이 있을 수도 있고 없을 수도 있다는 의미
    # 따라서 Update시 필요한 필드만 넣어서 Update할 수 있음
    name: Optional[str]
    email: Optional[EmailStr]
    course: Optional[str]
    gpa: Optional[float]

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "name": "Jane Doe",
                "email": "jdoe@example.com",
                "course": "Experiments, Science, and Fashion in Nanophotonics",
                "gpa": "3.0",
            }
        }

@app.post("/", response_description="Add new student", response_model=StudentModel)
async def create_student(student: StudentModel = Body(...)):
    student = jsonable_encoder(student) # 직렬화
    new_student = await db["students"].insert_one(student)
    created_student = await db["students"].find_one({"_id": new_student.inserted_id})
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=created_student)


@app.get(
    "/", response_description="List all students", response_model=List[StudentModel]
)
async def list_students():
    students = await db["students"].find().to_list(1000)
    return students


@app.get(
    "/{id}", response_description="Get a single student", response_model=StudentModel
)
async def show_student(id: str):
    if (student := await db["students"].find_one({"_id": id})) is not None:
        return student

    raise HTTPException(status_code=404, detail=f"Student {id} not found")


@app.put("/{id}", response_description="Update a student", response_model=StudentModel)
async def update_student(id: str, student: UpdateStudentModel = Body(...)):
    student = {k: v for k, v in student.dict().items() if v is not None}

    if len(student) >= 1:
        update_result = await db["students"].update_one({"_id": id}, {"$set": student})

        if update_result.modified_count == 1:
            if (
                updated_student := await db["students"].find_one({"_id": id})
            ) is not None:
                return updated_student

    if (existing_student := await db["students"].find_one({"_id": id})) is not None:
        return existing_student

    raise HTTPException(status_code=404, detail=f"Student {id} not found")


@app.delete("/{id}", response_description="Delete a student")
async def delete_student(id: str):
    delete_result = await db["students"].delete_one({"_id": id})

    if delete_result.deleted_count == 1:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(status_code=404, detail=f"Student {id} not found")
