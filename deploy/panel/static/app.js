const $ = (id) => document.getElementById(id);
const consola = $("log");
const barra = $("barra");
const botones = {
  ejecutar: $("btn-ejecutar"),
  validar: $("btn-validar"),
  limpiar: $("btn-limpiar"),
  cancelar: $("btn-cancelar"),
};
const modo = $("modo");

let desde = 0;
let enEjecucion = false;
let ultimoEstado = "inactivo";
let autoScroll = true;

const formato = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 0 });
const formatoEuro = new Intl.NumberFormat("es-ES", {
  style: "currency",
  currency: "USD",
  currencyDisplay: "code",
  maximumFractionDigits: 0,
});

function duracion(segundos) {
  if (segundos === null || segundos === undefined) return "—";
  const m = Math.floor(segundos / 60);
  const s = segundos % 60;
  return m > 0 ? `${m} min ${s} s` : `${s} s`;
}

function pintarLinea(texto) {
  const span = document.createElement("span");
  span.textContent = texto + "\n";
  if (/^\s*OK\s{2,}/.test(texto)) span.className = "ok";
  else if (/^\s*ERROR\s{2,}/.test(texto) || /Traceback|Error|error/.test(texto)) span.className = "error";
  else if (texto.startsWith("===")) span.className = "fase";
  else if (/Aviso:|Reintentando/.test(texto)) span.className = "aviso";
  consola.appendChild(span);
}

function agregarLineas(lineas) {
  if (!lineas.length) return;
  if (consola.dataset.vacio !== "1") {
    consola.textContent = "";
    consola.dataset.vacio = "1";
  }
  const cercaDelFinal = consola.scrollTop + consola.clientHeight >= consola.scrollHeight - 40;
  for (const linea of lineas) pintarLinea(linea);
  while (consola.childElementCount > 4000) consola.removeChild(consola.firstChild);
  if (cercaDelFinal && autoScroll) consola.scrollTop = consola.scrollHeight;
}

function pintarProgreso(estado) {
  const resumen = estado.resumen || { fase: 0, ok: 0, errores: 0, tablas: {} };
  const tablas = resumen.tablas || {};
  const esValidacion = estado.modo === "validar";
  let fase = esValidacion ? 4 : resumen.fase;
  if (estado.estado === "completado") fase = 4;
  const porcentaje =
    esValidacion && estado.estado !== "inactivo"
      ? 100
      : estado.estado === "error" && fase === 0
        ? 100
        : (fase / 4) * 100;

  barra.style.width = `${porcentaje}%`;
  barra.className = estado.estado === "error" ? "error" : estado.estado === "completado" ? "completado" : "";

  document.querySelectorAll(".pasos li").forEach((item) => {
    const numero = Number(item.dataset.paso);
    const hecho = esValidacion
      ? estado.estado === "completado" && numero === 4
      : numero < fase || estado.estado === "completado";
    item.classList.toggle("hecho", hecho);
    item.classList.toggle(
      "activo",
      estado.estado === "ejecutando" &&
        (esValidacion ? numero === 4 : numero === Math.min(4, fase + 1))
    );
  });

  $("num-ok").textContent = formato.format(resumen.ok);
  $("num-error").textContent = formato.format(resumen.errores);
  $("num-tablas").textContent = formato.format(Object.keys(tablas).length);
  $("tiempo").textContent = estado.duracion !== null ? duracion(estado.duracion) : "—";
}

function pintarEstado(estado) {
  const punto = $("punto");
  punto.className = `punto ${estado.estado}`;

  const titulos = {
    inactivo: "En espera",
    ejecutando: "Ejecutando ETL",
    completado: "Completado",
    error: "Terminó con errores",
    cancelado: "Cancelado",
  };
  $("estado-texto").textContent = titulos[estado.estado] || estado.estado;

  const resumen = estado.resumen || {};
  if (estado.estado === "ejecutando") {
    const paso = Math.min(4, (resumen.fase || 0) + 1);
    $("estado-detalle").textContent = `Paso ${paso} de 4 · modo ${estado.modo} · ${duracion(estado.duracion)}`;
  } else if (estado.estado === "completado") {
    $("estado-detalle").textContent = `${resumen.ok || 0} controles OK, ${resumen.errores || 0} con ERROR · ${duracion(estado.duracion)}`;
  } else if (estado.estado === "error") {
    $("estado-detalle").textContent = `${resumen.errores || 0} controles con ERROR. Revisa el registro.`;
  } else if (estado.estado === "cancelado") {
    $("estado-detalle").textContent = "La ejecución se detuvo antes de terminar.";
  } else {
    $("estado-detalle").textContent = "Elige el origen de datos y pulsa «Ejecutar ETL».";
  }

  const corriendo = estado.estado === "ejecutando";
  if (corriendo !== enEjecucion) {
    enEjecucion = corriendo;
    botones.ejecutar.disabled = corriendo;
    botones.validar.disabled = corriendo;
    botones.limpiar.disabled = corriendo;
    botones.cancelar.hidden = !corriendo;
    modo.disabled = corriendo;
  }

  $("log-nombre").textContent = estado.log ? estado.log : "sin ejecuciones";
  $("descargar-log").style.visibility = estado.log ? "visible" : "hidden";
  ultimoEstado = estado.estado;
  pintarProgreso(estado);
}

async function cargarEstado() {
  try {
    const respuesta = await fetch(`/api/estado?desde=${desde}`, { cache: "no-store" });
    if (!respuesta.ok) return;
    const estado = await respuesta.json();
    agregarLineas(estado.lineas || []);
    desde = estado.total || desde;
    pintarEstado(estado);
  } catch (error) {
    console.error("No se pudo consultar el estado", error);
  } finally {
    setTimeout(cargarEstado, enEjecucion ? 1000 : 3000);
  }
}

function fila(nombre, valor) {
  return `<div class="fila-dato"><span>${nombre}</span><strong>${valor}</strong></div>`;
}

async function consultarBase() {
  const contenedor = $("base-datos");
  try {
    const respuesta = await fetch("/api/base", { cache: "no-store" });
    const datos = await respuesta.json();
    const punto = $("base-punto");
    if (!datos.ok) {
      if (datos.vacia) {
        punto.className = "punto mini inactivo";
        contenedor.innerHTML = '<p class="tenue">La base está vacía. Ejecuta el ETL para cargarla.</p>';
      } else {
        punto.className = "punto mini error";
        contenedor.innerHTML = `<p class="tenue">Sin conexión o sin tablas cargadas.</p><p class="tenue">${datos.error || ""}</p>`;
      }
      return;
    }
    punto.className = "punto mini completado";
    const partes = [
      fila("Pedidos", formato.format(datos.pedidos)),
      fila("Líneas de pedido", formato.format(datos.lineas)),
      fila("Clientes", formato.format(datos.clientes)),
      fila("Productos", formato.format(datos.productos)),
      fila("Pagos", formato.format(datos.pagos)),
    ];
    if (datos.ventas !== null && datos.ventas !== undefined)
      partes.push(fila("Venta total (BI)", formatoEuro.format(datos.ventas)));
    if (datos.utilidad !== null && datos.utilidad !== undefined)
      partes.push(fila("Utilidad (BI)", formatoEuro.format(datos.utilidad)));
    if (datos.ultima_extraccion)
      partes.push(fila("Última extracción", new Date(datos.ultima_extraccion).toLocaleString("es-ES")));
    contenedor.innerHTML = partes.join("");
  } catch (error) {
    $("base-punto").className = "punto mini error";
    contenedor.innerHTML = '<p class="tenue">No se pudo consultar la base.</p>';
  }
}

async function cargarBase() {
  await consultarBase();
  setTimeout(cargarBase, 6000);
}

function mostrarAviso(texto, esError = false) {
  const aviso = $("aviso");
  if (!texto) {
    aviso.hidden = true;
    return;
  }
  aviso.textContent = texto;
  aviso.classList.toggle("error", esError);
  aviso.hidden = false;
}

async function cargarEntorno() {
  try {
    const respuesta = await fetch("/api/entorno", { cache: "no-store" });
    const entorno = await respuesta.json();
    const opcionCompleto = modo.querySelector('option[value="completo"]');
    const opcionCache = modo.querySelector('option[value="cache"]');

    if (!entorno.cache) {
      opcionCache.disabled = true;
      opcionCache.textContent = "Caché local (no disponible)";
      if (modo.value === "cache") modo.value = "completo";
    }
    if (!entorno.kaggle) {
      opcionCompleto.textContent = "Completo (faltan credenciales de Kaggle)";
    }

    if (!entorno.cache && !entorno.kaggle) {
      mostrarAviso(
        "No hay caché local ni credenciales de Kaggle: agrega KAGGLE_USERNAME y KAGGLE_KEY en deploy/.env o copia data/raw para poder ejecutar el ETL.",
        true
      );
    } else if (!entorno.kaggle) {
      mostrarAviso(
        "Sin credenciales de Kaggle: el modo completo fallará. Usa «Caché local» o define KAGGLE_USERNAME y KAGGLE_KEY.",
        false
      );
    } else if (!entorno.cache) {
      mostrarAviso("No hay datos en caché: la primera corrida debe ser en modo completo.", false);
    }
  } catch (error) {
    console.error(error);
  }
}

async function lanzar(nombreModo) {
  mostrarAviso("");
  try {
    const respuesta = await fetch("/api/ejecutar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ modo: nombreModo }),
    });
    const datos = await respuesta.json().catch(() => ({}));
    if (!respuesta.ok) {
      mostrarAviso(datos.detail || "No se pudo iniciar el proceso.", true);
      return;
    }
  } catch (error) {
    console.error(error);
    mostrarAviso(
      "No se pudo confirmar la respuesta del panel. Revisa el estado: puede que el proceso haya arrancado.",
      true
    );
    return;
  }

  // Solo se actualiza la interfaz después de confirmar que el servidor respondió.
  desde = 0;
  consola.textContent = "";
  consola.dataset.vacio = "1";
  enEjecucion = true;
  pintarEstado({ estado: "ejecutando", modo: nombreModo, resumen: { fase: 0, ok: 0, errores: 0, tablas: {} }, duracion: 0 });
}

botones.ejecutar.addEventListener("click", () => lanzar(modo.value));
botones.validar.addEventListener("click", () => lanzar("validar"));
const modalLimpiar = $("modal-limpiar");
const entradaLimpiar = $("confirmar-limpiar");
const botonConfirmarLimpiar = $("confirmar-limpiar-btn");

function abrirModalLimpiar() {
  entradaLimpiar.value = "";
  botonConfirmarLimpiar.disabled = true;
  modalLimpiar.showModal();
  entradaLimpiar.focus();
}

async function limpiarBase(texto) {
  botones.limpiar.disabled = true;
  try {
    const respuesta = await fetch("/api/limpiar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmar: texto }),
    });
    const datos = await respuesta.json().catch(() => ({}));
    if (!respuesta.ok) {
      mostrarAviso(datos.detail || "No se pudo limpiar la base.", true);
      return;
    }
    mostrarAviso(datos.mensaje || "Base limpiada.", false);
    await consultarBase();
  } catch (error) {
    console.error(error);
    mostrarAviso("No se pudo contactar con el panel.", true);
  } finally {
    botones.limpiar.disabled = false;
  }
}

entradaLimpiar.addEventListener("input", () => {
  botonConfirmarLimpiar.disabled = entradaLimpiar.value.trim().toUpperCase() !== "LIMPIAR";
});

entradaLimpiar.addEventListener("keydown", (evento) => {
  if (evento.key === "Enter" && !botonConfirmarLimpiar.disabled) {
    evento.preventDefault();
    botonConfirmarLimpiar.click();
  }
});

$("cancelar-limpiar").addEventListener("click", () => modalLimpiar.close());

botonConfirmarLimpiar.addEventListener("click", () => {
  const texto = entradaLimpiar.value.trim();
  modalLimpiar.close();
  limpiarBase(texto);
});

botones.limpiar.addEventListener("click", abrirModalLimpiar);
botones.cancelar.addEventListener("click", async () => {
  botones.cancelar.disabled = true;
  try {
    await fetch("/api/cancelar", { method: "POST" });
  } finally {
    setTimeout(() => (botones.cancelar.disabled = false), 2000);
  }
});

consola.addEventListener("scroll", () => {
  autoScroll = consola.scrollTop + consola.clientHeight >= consola.scrollHeight - 40;
});

fetch("/api/salud")
  .then((r) => r.json())
  .then((datos) => {
    if (datos.ok) {
      const version = datos.base.match(/PostgreSQL\s+[\d.]+/i);
      $("version-base").textContent = version ? version[0] : "PostgreSQL conectado";
    }
  })
  .catch(() => {});

cargarEntorno();
cargarBase();
cargarEstado();
