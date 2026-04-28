let selectedUserType = 'jobseeker'

function selectUserType(type) {
  selectedUserType = type
  const jobseekerCard = document.getElementById('jobseekerCard')
  const companyCard = document.getElementById('companyCard')

  if (type === 'jobseeker') {
    jobseekerCard.classList.add('active')
    companyCard.classList.remove('active')
  } else {
    companyCard.classList.add('active')
    jobseekerCard.classList.remove('active')
  }
}

function getRegForm() {
  htmx.ajax('POST', '/accounts/register/form/', {
    target: '#form-container',
    swap: 'innerHTML',
    values: { user_type: selectedUserType }
  })
}


// OTP input auto-focus and paste handling
document.addEventListener('DOMContentLoaded', () => {
  setupOtpInputs()
  setupPasswordStrength()
})

// Re-initialize after HTMX swaps
document.addEventListener('htmx:afterSwap', () => {
  setupOtpInputs()
  setupPasswordStrength()
})

function setupOtpInputs() {
  const otpContainer = document.getElementById('otp-container')
  if (!otpContainer) return

  const inputs = otpContainer.querySelectorAll('.otp-input')

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

function setupPasswordStrength() {
  const passwordInput = document.getElementById('id_password')
  if (!passwordInput) return

  const strengthBar = document.querySelector('.password-strength')
  const strengthText = document.querySelector('.password-strength-text')

  passwordInput.addEventListener('input', () => {
    const password = passwordInput.value
    const strength = calculatePasswordStrength(password)

    if (strengthBar) {
      strengthBar.style.width = strength.percent + '%'
      strengthBar.className = 'password-strength ' + strength.colorClass
    }
    if (strengthText) {
      strengthText.textContent = 'Password strength: ' + strength.label
    }
  })
}

function calculatePasswordStrength(password) {
  let score = 0
  if (password.length >= 8) score++
  if (password.length >= 12) score++
  if (/[A-Z]/.test(password)) score++
  if (/[0-9]/.test(password)) score++
  if (/[^A-Za-z0-9]/.test(password)) score++

  if (score <= 1) return { percent: 20, label: 'Very Weak', colorClass: 'bg-danger' }
  if (score === 2) return { percent: 40, label: 'Weak', colorClass: 'bg-warning' }
  if (score === 3) return { percent: 60, label: 'Fair', colorClass: 'bg-info' }
  if (score === 4) return { percent: 80, label: 'Good', colorClass: 'bg-primary' }
  return { percent: 100, label: 'Strong', colorClass: 'bg-success' }
}
