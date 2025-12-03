document.addEventListener('DOMContentLoaded', () => {
  let contentRoot = new URL(
    document.documentElement.dataset.content_root ?? DOCUMENTATION_OPTIONS.URL_ROOT,
    window.location.href,
  );

  function insertVersionSwitch(versions) {
    let versionElement = document.querySelector('.wy-side-nav-search > .version');
    if (!versionElement) return;

    let root = document.createElement('div');
    root.innerHTML = `
      <div class="switch-menus">
        <div class="version-switch"><select></select></div>
      </div>
    `;

    let switchMenus = root.firstElementChild;
    let versionSwitch = switchMenus.firstElementChild;
    let versionSwitchSelect = versionSwitch.firstElementChild;

    let versionElementStyles = getComputedStyle(versionElement);
    let cssStyleSheet = new CSSStyleSheet();
    cssStyleSheet.replaceSync(String.raw`
      .wy-side-nav-search > div.switch-menus {
        margin-top: ${versionElementStyles.marginTop};
        margin-bottom: ${versionElementStyles.marginBottom};
        color: ${versionElementStyles.color};

        div.version-switch {
          select {
            display: inline-block;
            margin-right: -2rem;
            padding-right: 2rem;
            text-align-last: center;
            background: none;
            border: none;
            border-radius: 0em;
            box-shadow: none;
            font-family: inherit;
            font-size: 1em;
            font-weight: normal;
            color: inherit;
            cursor: pointer;
            appearance: none;

            &:hover, &:active, &:focus {
              background: rgba(255, 255, 255, .1);
              color: rgba(255, 255, 255, .5);
            }

            option {
              color: black;
            }
          }

          &:has(> select):after {
            display: inline-block;
            width: 1.5em;
            height: 100%;
            padding: .1em;
            content: "\f0d7";
            font-size: 1em;
            line-height: 1.2em;
            font-family: FontAwesome;
            text-align: center;
            pointer-events: none;
            box-sizing: border-box;
          }
        }
      }
    `);
    document.adoptedStyleSheets.push(cssStyleSheet);

    let currentVersion = DOCUMENTATION_OPTIONS.VERSION;
    if (!versions.includes(currentVersion)) {
      versions = [
        { name: currentVersion, root_url: contentRoot },
        ...versions,
      ];
    }

    for (let { name, root_url: rootURL } of versions) {
      rootURL = new URL(rootURL, window.location.href);

      let versionOptionElement = document.createElement('option');
      versionOptionElement.textContent = name;
      versionOptionElement.dataset.url = rootURL;

      if (name === currentVersion) {
        versionOptionElement.selected = true;
      }

      versionSwitchSelect.appendChild(versionOptionElement);
    }

    versionSwitchSelect.addEventListener('change', (event) => {
      let option = event.target.selectedIndex;
      let item = event.target.options[option];
      window.location.href = item.dataset.url;
    });

    versionElement.replaceWith(switchMenus);
  }

  fetch(new URL('../versions.json', contentRoot)).then(async (response) => {
    if (response.status !== 200) return;
    let versions = await response.json();
    insertVersionSwitch(versions);
  });
});
