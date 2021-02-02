import os
import sys
import pytest
import numpy as np
import porespy as ps
import openpnm as op
from numpy.testing import assert_allclose
import psutil
from openpnm.io.__paraview__ import export_data
from openpnm.io.__paraview__ import open_paraview

class ExportTest():

    def setup_class(self):
        self.path = os.path.dirname(os.path.abspath(sys.argv[0]))
        
    def test_export_data(self):
        im = ps.generators.blobs(shape=[50, 50, 50], spacing=0.1)
        export_data(im=im, filename='test_to_paraview.pvsm')
        os.remove('test_to_paraview.pvsm')

    def test_open_paraview(self):
        open_paraview(filename='../fixtures/image.pvsm')
        if sys.platform != "darwin":
            assert "paraview" in (p.name().split('.')[0] for p in psutil.process_iter())


if __name__ == "__main__":
    t = ExportTest()
    self = t
    t.setup_class()
    for item in t.__dir__():
        if item.startswith("test"):
            print(f"Running test: {item}")
            t.__getattribute__(item)()
