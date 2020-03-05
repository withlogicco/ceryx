import re
import typesystem
import json

def ensure_protocol(url):
    starts_with_protocol = r"^https?://"
    return url if re.match(starts_with_protocol, url) else f"http://{url}"


def boolean_to_redis(value: bool):
    return "1" if value else "0"


def redis_to_boolean(value):
    return True if value == "1" else False


def object_to_redis(value: object):
    return json.dumps(value)


def redis_to_object(value):
    return json.loads(value)


def ensure_string(value):
    redis_value = (
        None if value is None
        else value.decode("utf-8") if type(value) == bytes else str(value)
    )
    return redis_value


def value_to_redis(field, value):
    if isinstance(field, typesystem.Boolean):
        return boolean_to_redis(value)
    
    if isinstance(field, typesystem.Reference):
        return field.target.validate(value).to_redis()

    if isinstance(field, typesystem.Object):
        return object_to_redis(value)

    return ensure_string(value)


def redis_to_value(field, redis_value):
    if isinstance(field, typesystem.Boolean):
        return redis_to_boolean(redis_value)
    
    if isinstance(field, typesystem.Reference):
        return field.target.from_redis(redis_value)

    if isinstance(field, typesystem.Object):
        return redis_to_object(redis_value)

    return ensure_string(redis_value)


class BaseSchema(typesystem.Schema):
    @classmethod
    def from_redis(cls, redis_data):
        data = {
            ensure_string(key): redis_to_value(cls.fields[ensure_string(key)], value)
            for key, value in redis_data.items()
        }
        return cls.validate(data)

    def to_redis(self):
        return {
            ensure_string(key): value_to_redis(self.fields[key], value)
            for key, value in self.items()
            if value is not None
        }


class Settings(BaseSchema):
    enforce_https = typesystem.Boolean(default=False)
    mode = typesystem.Choice(
        choices=(
            ("proxy", "Proxy"),
            ("redirect", "Redirect"),
        ),
        default="proxy",
    )
    headers = typesystem.Object(default={}, properties=typesystem.String(max_length=100))
    certificate_path = typesystem.String(allow_null=True)
    key_path = typesystem.String(allow_null=True)


class Route(BaseSchema):
    DEFAULT_SETTINGS = dict(Settings.validate({}))

    source = typesystem.String()
    target = typesystem.String()
    settings = typesystem.Reference(Settings, default=DEFAULT_SETTINGS)

    @classmethod
    def validate(cls, data):
        if "target" in data.keys():
            data["target"] = ensure_protocol(data["target"])
        return super().validate(data)
