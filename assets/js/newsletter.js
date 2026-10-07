// Sends the newsletter form to EmailOctopus and shows the answer in place.
(() => {
  const form = document.querySelector('[data-newsletter]');
  if (!form) return;
  const status = form.parentNode.querySelector('.newsletter-status');
  const button = form.querySelector('[type=submit]');

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    button.disabled = true;
    status.textContent = '';
    let ok = false;
    try {
      const response = await fetch(form.action, {
        method: 'POST', mode: 'cors', cache: 'no-cache', body: new FormData(form),
      });
      ok = (await response.json()).success === true;
    } catch (e) { /* network error or no JSON: handled below */ }
    if (ok) {
      form.hidden = true;
      status.textContent = form.dataset.success;
    } else {
      status.textContent = form.dataset.error;
      button.disabled = false;
    }
  });
})();
