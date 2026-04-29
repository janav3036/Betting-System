function toggleProfileDropdown() {
  document.getElementById('profileDropdown').classList.toggle('open');
}

document.addEventListener('click', function(e) {
  const wrapper = document.querySelector('.nav-profile-wrapper');
  if (!wrapper.contains(e.target)) {
    document.getElementById('profileDropdown').classList.remove('open');
  }
});