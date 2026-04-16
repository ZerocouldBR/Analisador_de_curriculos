import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiService } from '../services/api';
import { Company } from '../types';
import { useAuth } from './AuthContext';

interface CompanyContextType {
  company: Company | null;
  logoUrl: string | null;
  loading: boolean;
  refreshCompany: () => Promise<void>;
  uploadLogo: (file: File) => Promise<void>;
  deleteLogo: () => Promise<void>;
}

const CompanyContext = createContext<CompanyContextType>({
  company: null,
  logoUrl: null,
  loading: false,
  refreshCompany: async () => {},
  uploadLogo: async () => {},
  deleteLogo: async () => {},
});

export const useCompany = () => useContext(CompanyContext);

export const CompanyProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [company, setCompany] = useState<Company | null>(null);
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { user } = useAuth();

  const refreshCompany = useCallback(async () => {
    if (!user?.company_id) {
      setCompany(null);
      setLogoUrl(null);
      return;
    }

    try {
      setLoading(true);
      const data = await apiService.getMyCompany();
      setCompany(data);

      if (data.logo_url) {
        // Add timestamp to bust cache after upload
        setLogoUrl(apiService.getCompanyLogoUrl(data.id) + '?t=' + Date.now());
      } else {
        setLogoUrl(null);
      }
    } catch (error) {
      console.error('Error fetching company:', error);
      setCompany(null);
      setLogoUrl(null);
    } finally {
      setLoading(false);
    }
  }, [user?.company_id]);

  useEffect(() => {
    refreshCompany();
  }, [refreshCompany]);

  const uploadLogo = useCallback(async (file: File) => {
    if (!company) return;
    await apiService.uploadCompanyLogo(company.id, file);
    await refreshCompany();
  }, [company, refreshCompany]);

  const deleteLogo = useCallback(async () => {
    if (!company) return;
    await apiService.deleteCompanyLogo(company.id);
    setLogoUrl(null);
    await refreshCompany();
  }, [company, refreshCompany]);

  return (
    <CompanyContext.Provider value={{ company, logoUrl, loading, refreshCompany, uploadLogo, deleteLogo }}>
      {children}
    </CompanyContext.Provider>
  );
};
