if (window.flatpickr) {
  document.querySelectorAll('.task-datetime').forEach(input => {
    flatpickr(input, {
      locale: flatpickr.l10ns.es,
      enableTime: true,
      time_24hr: true,
      minuteIncrement: 5,
      disableMobile: true,
      allowInput: false,
      dateFormat: 'Y-m-d\\TH:i',
      altInput: true,
      altInputClass: 'task-datetime-display',
      altFormat: 'D, j M Y · H:i',
      onReady(_dates, _value, picker) {
        const label = document.querySelector(`label[for="${input.id}"]`);
        picker.altInput.id = `${input.id}_display`;
        picker.altInput.setAttribute('aria-label', label?.textContent.trim() || 'Fecha y hora');
        picker.altInput.placeholder = 'Seleccionar fecha y hora';
        if (label) label.htmlFor = picker.altInput.id;
      }
    });
  });
}
