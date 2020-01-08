from umongo import Document, MotorAsyncIOInstance
from umongo.fields import IntField, ListField, StringField

instance = MotorAsyncIOInstance()


@instance.register
class User(Document):
    chat_id = IntField(unique=True)
    first_name = StringField(allow_none=True)
    username = StringField(allow_none=True)
    last_name = StringField(allow_none=True)
    locale = StringField(allow_none=True)
    rooms = ListField(StringField())
    hotel_login = StringField()
    hotel_password = StringField()
