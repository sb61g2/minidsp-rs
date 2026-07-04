{
  lib,
  rustPlatform,
  stdenv,
  libusb1 ? null,
  pkg-config,
}:

rustPlatform.buildRustPackage {
  pname = "minidsp";
  version = "0.1.12";
  src = ./.;

  cargoBuildFlags = [ "-p minidsp -p minidsp-daemon" ];
  cargoLock.lockFile = ./Cargo.lock;

  doCheck = false;

  buildInputs = lib.optionals stdenv.isLinux [ libusb1 ];
  nativeBuildInputs = lib.optionals stdenv.isLinux [ pkg-config ];

  meta = with lib; {
    description = "A control interface for some MiniDSP products";
    homepage = "https://github.com/mrene/minidsp-rs";
    license = licenses.asl20;
    platforms = platforms.linux ++ platforms.darwin;
  };
}
