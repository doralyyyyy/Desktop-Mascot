const statusEl = document.getElementById("status");

async function main() {
  const app = new PIXI.Application({
    view: document.getElementById("stage"),
    resizeTo: window,
    autoStart: true,
    transparent: true,
    antialias: true,
    backgroundAlpha: 0,
  });

  const model = await PIXI.live2d.Live2DModel.from("models/model/model.model3.json", {
    autoInteract: false,
  });

  app.stage.addChild(model);

  function fitModel() {
    const bounds = model.getLocalBounds();
    const scale = Math.min(
      window.innerWidth / bounds.width,
      window.innerHeight / bounds.height,
    ) * 0.88;

    model.scale.set(scale);
    model.x = window.innerWidth / 2;
    model.y = window.innerHeight * 0.92;
    model.anchor.set(0.5, 1.0);
  }

  fitModel();
  window.addEventListener("resize", fitModel);

  model.motion("Idle", 0);
  statusEl.textContent = "Live2D model preview";
  setTimeout(() => {
    statusEl.style.display = "none";
  }, 2500);
}

main().catch((error) => {
  console.error(error);
  statusEl.textContent = `Live2D load failed: ${error.message || error}`;
});
