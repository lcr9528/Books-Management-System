from django.contrib.auth import get_user_model
from rest_framework import generics, permissions
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    RegisterAvailabilitySerializer,
    UserRegisterSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """读者自助注册，默认角色为读者。"""

    serializer_class = UserRegisterSerializer
    permission_classes = (permissions.AllowAny,)


class RegisterAvailabilityView(APIView):
    """注册前异步查重（不落库）。"""

    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        ser = RegisterAvailabilitySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        username = ser.validated_data["username"]
        email = ser.validated_data["email"]
        data = {}
        if username:
            data["username_available"] = not User.objects.filter(username__iexact=username).exists()
        if email:
            data["email_available"] = not User.objects.filter(email__iexact=email).exists()
        return Response(data)


class MeView(APIView):
    """当前登录用户信息（GET）与资料修改（PATCH，支持 multipart 上传头像）。"""

    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get(self, request):
        return Response(UserSerializer(request.user, context={"request": request}).data)

    def patch(self, request):
        ser = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(UserSerializer(request.user, context={"request": request}).data)
