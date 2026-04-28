let timerInterval = null
let timeLeft = 120

function updateStepIndicators(step) {
  const dots = document.querySelectorAll('.step-dot')
  if (!dots.length) return
  dots.forEach((dot, index) => {
    if (index + 1 <= step) {
      dot.classList.add('active')
    } else {
      dot.classList.remove('active')
    }
  })
}

function startTimer() {
  if (timerInterval) clearInterval(timerInterval)
  timeLeft = 120
  updateTimerDisplay()

  timerInterval = setInterval(() => {
    timeLeft--
    updateTimerDisplay()

    if (timeLeft <= 0) {
      clearInterval(timerInterval)
      const timerEl = document.getElementById('timer')
      if (timerEl) timerEl.textContent = '00:00'
    }
  }, 1000)
}

function updateTimerDisplay() {
  const timerEl = document.getElementById('timer')
  if (!timerEl) return
  const minutes = Math.floor(timeLeft / 60)
  const seconds = timeLeft % 60
  timerEl.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function togglePasswordField(inputId, button) {
  const passwordInput = document.getElementById(inputId)
  const icon = button.querySelector('i')

  if (!passwordInput) return

  if (passwordInput.type === 'password') {
    passwordInput.type = 'text'
    icon.classList.remove('bi-eye')
    icon.classList.add('bi-eye-slash')
  } else {
    passwordInput.type = 'password'
    icon.classList.remove('bi-eye-slash')
    icon.classList.add('bi-eye')
  }
}

// OTP input setup for password recovery
document.addEventListener('DOMContentLoaded', () => {
  setupRecoveryOtpInputs()
})

document.addEventListener('htmx:afterSwap', () => {
  setupRecoveryOtpInputs()
  if (document.getElementById('otp-container')) {
    startTimer()
  }
})

function setupRecoveryOtpInputs() {
  const otpContainer = document.getElementById('otp-container')
  if (!otpContainer) return

  const inputs = otpContainer.querySelectorAll('.form-control')

  inputs.forEach((input, index) => {
    input.addEventListener('input', (e) => {
      const value = e.target.value
      if (value.length === 1 && index < inputs.length - 1) {
        inputs[index + 1].focus()
      }
    })

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Backspace' && !e.target.value && index > 0) {
        inputs[index - 1].focus()
      }
      if (e.key === 'Enter') {
        e.preventDefault()
        const form = document.getElementById('verify-form')
        if (form) form.requestSubmit()
      }
    })

    input.addEventListener('paste', (e) => {
      e.preventDefault()
      const pasteData = e.clipboardData.getData('text').trim()
      if (/^\d{6}$/.test(pasteData)) {
        inputs.forEach((otpInput, i) => {
          otpInput.value = pasteData[i] || ''
        })
        inputs[5].focus()
      }
    })
  })
}