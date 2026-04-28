from dmr.routing import path

from server.apps.accounts import views

urlpatterns = [
    path(
        'register/',
        views.RegisterView.as_view(),
        name='register',
    ),
    path(
        'register/form/',
        views.RegisterFormView.as_view(),
        name='register_form',
    ),
    path(
        'register/submit/',
        views.RegisterSubmitView.as_view(),
        name='register_submit',
    ),
    path(
        'register/verify/',
        views.VerifyCodeView.as_view(),
        name='verify_code',
    ),
    path(
        'register/resend/',
        views.ResendVerificationView.as_view(),
        name='resend_verification',
    ),
    path(
        'login/',
        views.LoginView.as_view(),
        name='login',
    ),
    path(
        'password-recovery/',
        views.PasswordRecoveryView.as_view(),
        name='password_recovery',
    ),
    path(
        'password-recovery/verify/',
        views.PasswordRecoveryVerifyView.as_view(),
        name='password_recovery_verify',
    ),
    path(
        'password-recovery/resend/',
        views.PasswordRecoveryResendView.as_view(),
        name='password_recovery_resend',
    ),
    path(
        'password-recovery/reset/',
        views.PasswordRecoveryResetView.as_view(),
        name='password_recovery_reset',
    ),
]
