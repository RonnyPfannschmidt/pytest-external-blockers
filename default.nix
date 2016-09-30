{pkgs ? import <nixos> {}}:
with pkgs.python35Packages;

buildPythonPackage {
    buildInputs = [pkgs.git setuptools_scm ipython];
    propagatedBuildInputs = [python pytest];
    name= "pytest_external_blockers";
    src = ./.;
    checkPhase=''
        py.test testing
    '';
}