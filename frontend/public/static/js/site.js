/* Interações do site. Tudo é progressivo: sem JS, o conteúdo aparece normalmente. */
(() => {
  const root = document.documentElement;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* Menu mobile ---------------------------------------------------------- */
  const toggle = document.querySelector(".nav-toggle");
  const nav = document.getElementById("nav");
  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(open));
    });
    nav.addEventListener("click", (e) => {
      if (e.target.closest("a")) { nav.classList.remove("is-open"); toggle.setAttribute("aria-expanded", "false"); }
    });
  }

  /* Seletor de idioma --------------------------------------------------- */
  document.querySelectorAll("[data-lang-switch]").forEach((box) => {
    const btn = box.querySelector(".lang-btn");
    const setOpen = (open) => { box.classList.toggle("is-open", open); btn.setAttribute("aria-expanded", String(open)); };
    btn.addEventListener("click", () => setOpen(!box.classList.contains("is-open")));
    document.addEventListener("click", (e) => { if (!box.contains(e.target)) setOpen(false); });
    box.addEventListener("keydown", (e) => { if (e.key === "Escape") { setOpen(false); btn.focus(); } });
  });

  /* Vídeo de Nosotros: capa própria; os controles nativos só aparecem ao tocar */
  document.querySelectorAll("[data-video]").forEach((box) => {
    const video = box.querySelector("video");
    video.controls = false;
    box.querySelector(".about-video-cover").addEventListener("click", () => {
      box.classList.add("is-playing");
      video.controls = true;
      video.play();
    });
  });

  /* Texto em palavras (revelação do parágrafo de abertura) ---------------- */
  document.querySelectorAll("[data-split]").forEach((el) => {
    const words = el.textContent.trim().split(/\s+/);
    el.textContent = "";
    words.forEach((w, i) => {
      const span = document.createElement("span");
      span.className = "word";
      span.style.setProperty("--wd", `${Math.min(i * 22, 1200)}ms`);
      span.textContent = w;
      el.append(span, document.createTextNode(" "));
    });
  });

  /* Ícones desenhados como giz ------------------------------------------- */
  document.querySelectorAll(".pillar-icon svg *").forEach((path) => {
    if (typeof path.getTotalLength === "function") {
      try { path.style.setProperty("--len", Math.ceil(path.getTotalLength()) || 200); } catch (e) { /* noop */ }
    }
  });

  /* Revelações ao entrar na tela ----------------------------------------- */
  const targets = document.querySelectorAll("[data-reveal], [data-split]");
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) { entry.target.classList.add("is-in"); io.unobserve(entry.target); }
      });
    }, { rootMargin: "0px 0px -12% 0px", threshold: 0.15 });
    targets.forEach((t) => io.observe(t));
  } else {
    targets.forEach((t) => t.classList.add("is-in"));
  }

  /* Contadores ----------------------------------------------------------- */
  const animateCount = (el) => {
    const raw = el.dataset.counter || el.textContent;
    const digits = raw.replace(/\D/g, "");
    if (!digits || reduced) return;
    const end = parseInt(digits, 10);
    const [before, after] = raw.split(digits);
    const duration = 1600;
    const start = performance.now();
    const step = (now) => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = before + Math.round(end * eased).toLocaleString(root.lang || "es") + after;
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  const counters = document.querySelectorAll("[data-counter]");
  if (counters.length && "IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) { animateCount(entry.target); io.unobserve(entry.target); }
      });
    }, { threshold: 0.6 });
    counters.forEach((c) => io.observe(c));
  }

  /* Header, barra de progresso, parallax e seção ativa -------------------- */
  const header = document.querySelector(".site-header");
  const progress = document.querySelector(".progress");
  const parallaxes = [...document.querySelectorAll("[data-parallax]")];
  const links = [...document.querySelectorAll('.nav a[href*="#"]')];
  const sections = links
    .map((a) => document.querySelector(`#${a.getAttribute("href").split("#")[1]}`))
    .filter(Boolean);

  let ticking = false;
  const onScroll = () => {
    const y = window.scrollY;
    if (header) header.classList.toggle("is-solid", y > 40);
    if (progress) {
      const max = document.body.scrollHeight - window.innerHeight;
      progress.style.transform = `scaleX(${max > 0 ? y / max : 0})`;
    }
    if (!reduced) {
      parallaxes.forEach((el) => {
        const rect = el.parentElement.getBoundingClientRect();
        if (rect.bottom > -200 && rect.top < window.innerHeight + 200) {
          const offset = (rect.top - window.innerHeight / 2) * -parseFloat(el.dataset.parallax || "0.2");
          el.style.transform = `translate3d(0, ${offset.toFixed(1)}px, 0)`;
        }
      });
    }
    let current = null;
    sections.forEach((sec) => { if (sec.getBoundingClientRect().top <= window.innerHeight * 0.4) current = sec.id; });
    links.forEach((a) => a.classList.toggle("is-active", !!current && a.getAttribute("href").endsWith(`#${current}`)));
    ticking = false;
  };
  window.addEventListener("scroll", () => {
    if (!ticking) { ticking = true; requestAnimationFrame(onScroll); }
  }, { passive: true });
  window.addEventListener("resize", onScroll);
  onScroll();
})();
