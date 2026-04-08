import os
import sys

def get_cors_headers():
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }

def main(params):
    """
    Export Action Wrapper de IBM Cloud.
    Recibe los datos base completos de frontend en 'analysis_data'.
    """
    if params.get("__ow_method") == "options":
        return {"headers": get_cors_headers(), "statusCode": 204, "body": ""}
        
    try:
        req_format = params.get("format", "geojson")
        analysis_data = params.get("analysis_data", {})
        
        if req_format == "pdf_ready":
            # Extraer dict para pasarlo a export. Retorna json con pdf config.
            executive_report = analysis_data.get("executive_report", {})
            metadata = analysis_data.get("metadata", {})
            scenarios = analysis_data.get("scenarios", {})
            
            # Replicar el formato pdf_ready de BusinessAgent
            pdf_dict = {
                "business_resumen": executive_report.get("resumen_ejecutivo", ""),
                "business_recomendacion": executive_report.get("recomendacion_final", ""),
                "business_advertencias": executive_report.get("advertencias", []),
                "business_pasos": executive_report.get("proximos_pasos", []),
                "business_escenarios": scenarios,
                "analysis_id": analysis_data.get("analysis_id", "N/A"),
                "metadata": metadata
            }
            return {
                "headers": get_cors_headers(),
                "statusCode": 200,
                "body": pdf_dict
            }
            
        else:
            # GEOJSON Merge
            demand_geo = analysis_data.get("demand_geojson", {"type": "FeatureCollection", "features": []})
            risk_geo = analysis_data.get("risk_geojson", {"features": []})
            viability_scores = analysis_data.get("viability_scores", [])
            
            risk_map = {f["id"]: f for f in risk_geo.get("features", []) if "id" in f}
            viability_map = {f["id"]: f for f in viability_scores}
            
            # Mutar iterativamete (shallow safe since it's going via json dump soon inside IBM HTTP response)
            for feat in demand_geo.get("features", []):
                props = feat.setdefault("properties", {})
                fid = props.get("id") or feat.get("id")
                
                # Riesgo
                r_node = risk_map.get(fid)
                if r_node:
                    rp = r_node.get("properties", {})
                    props["score_riesgo"] = rp.get("score_riesgo")
                    props["clasificacion_riesgo"] = rp.get("clasificacion")
                    
                # Viabilidad
                v_node = viability_map.get(fid)
                if v_node:
                    props["score_viabilidad"] = v_node.get("score_viabilidad")
                    props["clasificacion_negocios"] = v_node.get("clasificacion")
            
            return {
                "headers": get_cors_headers(),
                "statusCode": 200,
                "body": demand_geo
            }
            
    except Exception as e:
        return {
            "headers": get_cors_headers(),
            "statusCode": 500,
            "body": {"error": f"Error orquestando export action: {str(e)}"}
        }

