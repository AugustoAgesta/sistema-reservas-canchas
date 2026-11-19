(function () {
  'use strict';

  const canchas = [
    { nombre: 'Fútbol 5', piso: 'Césped sintético', techo: true, precio: 1200, foto: 'futbol-5.webp' },
    { nombre: 'Fútbol 11', piso: 'Césped natural', techo: false, precio: 1000, foto: 'futbol-11.webp' },
    { nombre: 'Futsal', piso: 'Madera', techo: true, precio: 1500, foto: 'futsal.webp' },
  ];
  const horas = ['09:00', '10:00', '11:00', '17:00', '18:00', '19:00', '20:00', '21:00', '22:00'];
  const estados = { disponible: 'Libre', ocupado: 'Reservado', bloqueado: 'Bloqueado' };
  const moneda = new Intl.NumberFormat('es-UY', { style: 'currency', currency: 'UYU', maximumFractionDigits: 0 });
  const fechaLocal = new Intl.DateTimeFormat('es-UY', { dateStyle: 'full', timeZone: 'UTC' });
  const el = id => document.getElementById(id);
  const fecha = el('fecha');
  const reservas = new Set();
  let filtro = -1;
  let cancha = -1;
  let turno = '';

  function moverDia(dia, cambio) {
    const valor = new Date(`${dia}T12:00:00Z`);
    valor.setUTCDate(valor.getUTCDate() + cambio);
    return valor.toISOString().slice(0, 10);
  }

  // La demo empieza mañana, con todos los horarios de ejemplo aún por delante.
  const hoy = new Intl.DateTimeFormat('sv-SE', { timeZone: 'America/Montevideo' }).format(new Date());
  fecha.min = moverDia(hoy, 1);
  fecha.max = moverDia(hoy, 90);
  fecha.value = fecha.min;

  function icono(id) {
    return `<svg class="icono" aria-hidden="true"><use href="static/img/iconos.svg#${id}"></use></svg>`;
  }

  function atributos(c) {
    return `<span>${icono('floor')}${c.piso}</span><span>${icono(c.techo ? 'roof' : 'sun')}${c.techo ? 'Techada' : 'Al aire libre'}</span>`;
  }

  function clave(id, hora) {
    return `${fecha.value}/${id}/${hora}`;
  }

  function estado(id, hora) {
    if (reservas.has(clave(id, hora))) return 'ocupado';
    const dia = new Date(`${fecha.value}T12:00:00Z`).getUTCDate();
    if (id === dia % canchas.length && horas.indexOf(hora) < 2) return 'bloqueado';
    if (hora === horas[3 + ((dia + id) % 6)]) return 'ocupado';
    return 'disponible';
  }

  function mostrarCatalogo() {
    el('catalogo-lista').innerHTML = canchas.map((c, id) => {
      if (filtro !== -1 && filtro !== id) return '';
      const libres = horas.filter(hora => estado(id, hora) === 'disponible').length;
      return `<article class="card-cancha">
        <div class="foto-card">
          <img src="static/img/${c.foto}" alt="${c.nombre}, ${c.piso.toLowerCase()}" width="600" height="360">
          <span class="formato disponibilidad"><i></i>${libres} ${libres === 1 ? 'turno libre' : 'turnos libres'}</span>
        </div>
        <div class="card-datos">
          <h3>${c.nombre}</h3><div class="atributos">${atributos(c)}</div>
          <div class="card-pie">
            <span class="precio">${moneda.format(c.precio)} <small>/ hora</small></span>
            <a class="turno-link" href="#reserva" data-cancha="${id}" aria-label="Ver horarios de ${c.nombre}">Ver horarios ${icono('arrow')}</a>
          </div>
        </div>
      </article>`;
    }).join('');
    el('cantidad').textContent = filtro === -1 ? `${canchas.length} canchas` : '1 cancha';
  }

  function mostrarTurnos() {
    if (cancha < 0) return;
    const c = canchas[cancha];
    el('detalle').innerHTML = `<img class="foto-grande" src="static/img/${c.foto}" alt="${c.nombre}"><div class="detalle-texto">
      <h3>${c.nombre}</h3><div class="atributos">${atributos(c)}</div>
      <p class="precio">${moneda.format(c.precio)} <small>/ hora</small></p></div>`;
    el('horarios').innerHTML = horas.map(hora => {
      const situacion = estado(cancha, hora);
      if (situacion === 'disponible') {
        return `<button type="button" data-hora="${hora}" aria-pressed="${turno === hora}"><strong>${hora}</strong><small>Libre</small></button>`;
      }
      return `<span class="slot ${situacion}"><strong>${hora}</strong><small>${estados[situacion]}</small></span>`;
    }).join('');
    el('confirmar').hidden = !turno;
    el('resumen-reserva').textContent = turno ? `${c.nombre} · ${turno} h · ${moneda.format(c.precio)}` : '';
  }

  function mostrarAgenda() {
    const columnas = canchas.map((c) => `<th scope="col">${c.nombre}</th>`).join('');
    el('agenda-columnas').innerHTML = `<tr><th scope="col">Hora</th>${columnas}</tr>`;
    const totales = { disponible: 0, ocupado: 0, bloqueado: 0 };
    el('agenda-turnos').innerHTML = horas.map(hora => {
      const celdas = canchas.map((_, id) => {
        const situacion = estado(id, hora);
        totales[situacion] += 1;
        return `<td><span class="estado ${situacion}"><i></i>${estados[situacion]}</span></td>`;
      }).join('');
      return `<tr><th scope="row">${hora}</th>${celdas}</tr>`;
    }).join('');
    const metricas = [
      ['ticket', 'Reservas vigentes', totales.ocupado],
      ['pitch', 'Turnos libres', totales.disponible],
      ['block', 'Turnos bloqueados', totales.bloqueado],
    ];
    el('totales').innerHTML = metricas.map(([id, etiqueta, cantidad]) =>
      `<div>${icono(id)}<span>${etiqueta}</span><strong>${cantidad}</strong></div>`
    ).join('');
  }

  function actualizarDia() {
    if (!fecha.checkValidity()) fecha.value = fecha.min;
    turno = '';
    el('confirmacion').replaceChildren();
    const dia = fechaLocal.format(new Date(`${fecha.value}T12:00:00Z`));
    el('dia-agenda').textContent = dia;
    el('dia-reserva').textContent = dia;
    el('anterior').disabled = fecha.value === fecha.min;
    el('siguiente').disabled = fecha.value === fecha.max;
    mostrarCatalogo();
    mostrarTurnos();
    mostrarAgenda();
  }

  const filtros = el('filtros');
  filtros.innerHTML = ['Todas', ...canchas.map(c => c.nombre)].map((nombre, indice) =>
    `<button type="button" data-filtro="${indice - 1}" aria-pressed="${indice === 0}">${nombre}</button>`
  ).join('');
  filtros.addEventListener('click', event => {
    const boton = event.target.closest('[data-filtro]');
    if (!boton) return;
    filtro = Number(boton.dataset.filtro);
    for (const ajuste of filtros.querySelectorAll('button')) {
      ajuste.setAttribute('aria-pressed', String(ajuste === boton));
    }
    mostrarCatalogo();
  });
  el('catalogo-lista').addEventListener('click', event => {
    const enlace = event.target.closest('[data-cancha]');
    if (!enlace) return;
    cancha = Number(enlace.dataset.cancha);
    turno = '';
    el('confirmacion').replaceChildren();
    el('reserva').hidden = false;
    mostrarTurnos();
    el('titulo-reserva').focus({ preventScroll: true });
  });
  el('horarios').addEventListener('click', event => {
    const boton = event.target.closest('[data-hora]');
    if (!boton) return;
    turno = boton.dataset.hora;
    for (const opcion of el('horarios').querySelectorAll('button')) {
      opcion.setAttribute('aria-pressed', String(opcion === boton));
    }
    el('confirmacion').replaceChildren();
    el('confirmar').hidden = false;
    el('resumen-reserva').textContent = `${canchas[cancha].nombre} · ${turno} h · ${moneda.format(canchas[cancha].precio)}`;
  });
  el('confirmar').addEventListener('submit', event => {
    event.preventDefault();
    if (!turno || estado(cancha, turno) !== 'disponible') return;
    reservas.add(clave(cancha, turno));
    const texto = `Reserva simulada para ${canchas[cancha].nombre} a las ${turno}. Ya se refleja en la agenda.`;
    turno = '';
    mostrarCatalogo();
    mostrarTurnos();
    mostrarAgenda();
    const confirmacion = el('confirmacion');
    confirmacion.className = 'aviso';
    confirmacion.textContent = texto;
    confirmacion.tabIndex = -1;
    confirmacion.focus();
  });
  fecha.addEventListener('change', actualizarDia);
  for (const [id, paso] of [['anterior', -1], ['siguiente', 1]]) {
    el(id).addEventListener('click', () => {
      fecha.value = moverDia(fecha.value, paso);
      actualizarDia();
    });
  }
  actualizarDia();
})();
