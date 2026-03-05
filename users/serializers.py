from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User


# user serializer

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'phone', 'address', 'profile_pic', 'role']
        

# user register serializer

class RegisterSerializer(serializers.ModelSerializer):

    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "full_name",
            "phone",
            "address",
            "profile_pic",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        return user



# user login serializer

class LoginSerializer(serializers.Serializer):

    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):

        user = authenticate(
            username=data["email"],
            password=data["password"]
        )

        if not user:
            raise serializers.ValidationError("Invalid credentials")

        data["user"] = user
        return data
    

# password change serializer
class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate_new_password(self, value):
        validate_password(value, user=self.context['request'].user)
        return value
