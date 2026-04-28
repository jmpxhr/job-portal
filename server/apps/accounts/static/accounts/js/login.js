function switchUserType(type) {
  const candidateTab = document.getElementById('candidateTab')
  const employerTab = document.getElementById('employerTab')
  const userTypeInput = document.getElementById('id_user_type')

  if (type === 'jobseeker') {
    candidateTab.classList.add('active')
    employerTab.classList.remove('active')
  } else {
    employerTab.classList.add('active')
    candidateTab.classList.remove('active')
  }

  if (userTypeInput) {
    userTypeInput.value = type
  }
}

function togglePassword(button) {
  const inputGroup = button.closest('.input-group')
  const passwordInput = inputGroup.querySelector('input[type="password"], input[data-type="password"]')
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