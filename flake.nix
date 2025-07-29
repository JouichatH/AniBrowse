{
  description = "FastAnime Project Flake";

  inputs = {
    # The nixpkgs unstable latest commit breaks the plyer python package
    nixpkgs.url = "github:nixos/nixpkgs/3ff0e34b1383648053bba8ed03f201d3466f90c9";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        inherit (pkgs) lib python3Packages;

        version = "3.0.0";
      in
      {
        packages.default = python3Packages.buildPythonApplication {
          pname = "fastanime";
          inherit version;
          pyproject = true;

          src = self;

          build-system = with python3Packages; [ hatchling ];

          dependencies = with python3Packages; [
            click
            inquirerpy
            requests
            rich
            thefuzz
            yt-dlp
            dbus-python
            hatchling
            plyer
            mpv
            fastapi
            pycryptodome
            pypresence
            httpx
          ];

          postPatch = ''
            substituteInPlace pyproject.toml \
              --replace-fail "pydantic>=2.11.7" "pydantic>=2.11.4"
          '';

          makeWrapperArgs = [
            "--prefix PATH : ${
              lib.makeBinPath (
                with pkgs;
                [
                  mpv
                ]
              )
            }"
          ];

          # Needs to be adapted for the nix derivation build
          doCheck = false;

          pythonImportsCheck = [ "fastanime" ];

          meta = {
            description = "Your browser anime experience from the terminal";
            homepage = "https://github.com/Benexl/FastAnime";
            changelog = "https://github.com/Benexl/FastAnime/releases/tag/v${version}";
            mainProgram = "fastanime";
            license = lib.licenses.unlicense;
            maintainers = with lib.maintainers; [ theobori ];
          };
        };

        devShells.default = pkgs.mkShell {
          venvDir = ".venv";

          env.LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [ pkgs.libxcrypt-legacy ];

          packages =
            with pkgs;
            [
              mpv
              fzf
              rofi
              uv
              pyright
            ]
            ++ (with python3Packages; [
              venvShellHook
              hatchling
            ])
            ++ self.packages.${system}.default.dependencies;
        };
      }
    );
}
