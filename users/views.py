from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token

from .serializers import RegisterSerializer, LoginSerializer, PasswordChangeSerializer
from .permissions import IsAdmin, IsUser, IsAdminOrUser



# user register view
class RegisterView(APIView):

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "user": user.email,
                "message": "User registered successfully"
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
# user login view
class LoginView(APIView):

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data["user"]
            token, _ = Token.objects.get_or_create(user=user)

            return Response({
                "token": token.key,
                "role": user.role,
                "message": "User logged in successfully"
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
# password change view

class PasswordChangeView(APIView):
    permission_classes = [IsAdminOrUser]

    def post(self, request):
        # Pass the request in context so the serializer can access request.user
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({"message": "Password updated successfully"}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

