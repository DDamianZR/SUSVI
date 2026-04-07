import React from 'react';
import MapaInteractivo from '../components/MapaInteractivo';
import PanelMetricas from '../components/PanelMetricas';
import SelectorEscenario from '../components/SelectorEscenario';
import ModuloCiudadano from '../components/ModuloCiudadano';

function Dashboard() {
  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      <div style={{ flex: 1 }}>
        <MapaInteractivo />
      </div>
      <div style={{ width: 360, overflowY: 'auto', padding: 16 }}>
        <SelectorEscenario />
        <PanelMetricas />
        <ModuloCiudadano />
      </div>
    </div>
  );
}

export default Dashboard;
