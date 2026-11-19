const pago = document.querySelector('#pago-web');
const importe = document.querySelector('#importe');

if (pago && importe) {
  const actualizarTotal = () => {
    importe.textContent = pago.checked ? importe.dataset.web : importe.dataset.base;
  };
  pago.addEventListener('change', actualizarTotal);
  window.addEventListener('pageshow', actualizarTotal);
}
