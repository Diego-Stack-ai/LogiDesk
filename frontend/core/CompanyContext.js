// frontend/core/CompanyContext.js
export const CompanyContext = {
    COMPANY_ID: "NzXaCgyXxZWWehw1tSlo",
    
    getCompanyPath: function() { return `aziende/${this.COMPANY_ID}`; },
    
    getTenantPath: function(tenantId) { return `aziende/${this.COMPANY_ID}/tenants/${tenantId}`; },
    
    getSettingsPath: function(domain) { return `aziende/${this.COMPANY_ID}/settings/${domain}`; },
    
    getTenantSettingsPath: function(tenantId, domain) { return `aziende/${this.COMPANY_ID}/tenants/${tenantId}/settings/${domain}`; },
    
    getEmployeesPath: function() { return `aziende/${this.COMPANY_ID}/dipendenti`; },
    
    getUsersPath: function() { return `aziende/${this.COMPANY_ID}/utenti`; },
    
    getVehiclesPath: function() { return `aziende/${this.COMPANY_ID}/mezzi`; },
    
    getDeliveryPointsPath: function(tenantId) { return `aziende/${this.COMPANY_ID}/tenants/${tenantId}/punti_consegna`; },
    
    getImportMappingsPath: function(tenantId) { return `aziende/${this.COMPANY_ID}/tenants/${tenantId}/import_mappings`; }
};

export default CompanyContext;
