"""Generated AR/PBR smoke-test scenes."""
from __future__ import annotations

from pathlib import Path


PBR_FBX_SCENE = """
; FBX 7.4.0 project file
FBXHeaderExtension:  {
    FBXHeaderVersion: 1003
    FBXVersion: 7400
}
GlobalSettings:  {
    Properties70:  {
        P: "UnitScaleFactor", "double", "Number", "",100
        P: "UpAxis", "int", "Integer", "",1
        P: "UpAxisSign", "int", "Integer", "",1
        P: "FrontAxis", "int", "Integer", "",2
        P: "FrontAxisSign", "int", "Integer", "",-1
        P: "CoordAxis", "int", "Integer", "",0
        P: "CoordAxisSign", "int", "Integer", "",1
    }
}
Objects:  {
    Geometry: 1000, "Geometry::MatteRoadPanel", "Mesh" {
        Vertices: *12 {
            a: -2.2,-1.2,0, -0.2,-1.2,0, -0.2,1.2,0, -2.2,1.2,0
        }
        PolygonVertexIndex: *4 {
            a: 0,1,2,-4
        }
    }
    Geometry: 1100, "Geometry::MetallicSignPanel", "Mesh" {
        Vertices: *12 {
            a: 0.25,-1.2,0, 2.25,-1.2,0, 2.25,1.2,0, 0.25,1.2,0
        }
        PolygonVertexIndex: *4 {
            a: 0,1,2,-4
        }
    }
    Geometry: 1200, "Geometry::CenterPrism", "Mesh" {
        Vertices: *15 {
            a: -0.45,-0.45,0.15, 0.45,-0.45,0.15, 0.45,0.45,0.15, -0.45,0.45,0.15, 0,0,1.25
        }
        PolygonVertexIndex: *16 {
            a: 0,1,2,-4, 0,1,-5, 1,2,-5, 2,3,-5, 3,0,-5
        }
    }
    Model: 2000, "Model::MatteRoadPanel", "Mesh" {
        Properties70:  {
            P: "Lcl Translation", "Lcl Translation", "", "A",0,0,0
        }
    }
    Model: 2100, "Model::MetallicSignPanel", "Mesh" {
        Properties70:  {
            P: "Lcl Translation", "Lcl Translation", "", "A",0,0,0
        }
    }
    Model: 2200, "Model::CenterPrism", "Mesh" {
        Properties70:  {
            P: "Lcl Translation", "Lcl Translation", "", "A",0,0,0
        }
    }
    Material: 3000, "Material::RoughAsphalt", "" {
        Properties70:  {
            P: "Maya|base_color", "ColorRGB", "Color", "",0.08,0.09,0.08
            P: "Maya|roughness", "double", "Number", "",0.92
            P: "Maya|metallic", "double", "Number", "",0.0
            P: "Maya|specular", "double", "Number", "",0.18
        }
    }
    Material: 3100, "Material::BrushedMetal", "" {
        Properties70:  {
            P: "Maya|base_color", "ColorRGB", "Color", "",0.65,0.70,0.78
            P: "Maya|roughness", "double", "Number", "",0.22
            P: "Maya|metallic", "double", "Number", "",1.0
            P: "Maya|specular", "double", "Number", "",0.85
        }
    }
    Material: 3200, "Material::OrangePaint", "" {
        Properties70:  {
            P: "Maya|base_color", "ColorRGB", "Color", "",1.0,0.31,0.06
            P: "Maya|roughness", "double", "Number", "",0.38
            P: "Maya|metallic", "double", "Number", "",0.0
            P: "Maya|specular", "double", "Number", "",0.55
        }
    }
}
Connections:  {
    C: "OO",1000,2000
    C: "OO",1100,2100
    C: "OO",1200,2200
    C: "OO",3000,2000
    C: "OO",3100,2100
    C: "OO",3200,2200
}
"""


def write_pbr_fbx_scene(path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(PBR_FBX_SCENE.strip() + "\n", encoding="utf-8")
    return out
