import { useState, useMemo } from 'react';

export function useMapData(analysisResult) {
  const [activeLayer, setActiveLayer] = useState('viability'); // 'demand' | 'risk' | 'viability'
  const [selectedZone, setSelectedZone] = useState(null);

  const mapProps = useMemo(() => {
    if (!analysisResult) {
      return {
        demandGeoJSON: null,
        riskGeoJSON: null,
        viabilityScores: []
      };
    }

    return {
      demandGeoJSON: analysisResult.demand_geojson,
      riskGeoJSON: analysisResult.risk_geojson,
      viabilityScores: analysisResult.viability_scores || [],
    };
  }, [analysisResult]);

  return {
    ...mapProps,
    activeLayer,
    setActiveLayer,
    selectedZone,
    setSelectedZone
  };
}
