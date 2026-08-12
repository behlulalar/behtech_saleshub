import { useState } from 'react';
import AiActionProposals from './ai/AiActionProposals';
import AiDe4ActionsInbox from './ai/AiDe4ActionsInbox';
import AiOpsPanel from './ai/AiOpsPanel';
import AiPriorityList from './ai/AiPriorityList';
import CompanyIntelligenceCard from './ai/CompanyIntelligenceCard';
import SalesAssistantPage from './ai/SalesAssistantPage';
import SalesDiagnosesCard from './ai/SalesDiagnosesCard';
import type { IntelligenceView } from '../types';

interface Props {
  view: IntelligenceView;
  isOwner: boolean;
  onEditLead: (leadId: number) => void;
}

export default function IntelligencePage({ view, isOwner, onEditLead }: Props) {
  const [proposalRefresh, setProposalRefresh] = useState(0);

  if (!isOwner) {
    return null;
  }

  const bumpProposals = () => setProposalRefresh((n) => n + 1);

  switch (view) {
    case 'intel-overview':
      return (
        <div className="min-w-0 space-y-6 max-lg:space-y-4">
          <CompanyIntelligenceCard isOwner={isOwner} />
          <AiPriorityList
            isOwner={isOwner}
            onOpenLead={onEditLead}
            onProposalQueued={bumpProposals}
          />
          <AiOpsPanel isOwner={isOwner} />
        </div>
      );
    case 'intel-diagnoses':
      return (
        <div className="min-w-0 space-y-6 max-lg:space-y-4">
          <SalesDiagnosesCard onEditLead={onEditLead} onDe4ActionChanged={bumpProposals} />
        </div>
      );
    case 'intel-actions':
      return (
        <div className="min-w-0 space-y-6 max-lg:space-y-4">
          <AiDe4ActionsInbox
            isOwner={isOwner}
            onOpenLead={onEditLead}
            refreshToken={proposalRefresh}
          />
          <AiActionProposals
            isOwner={isOwner}
            onOpenLead={onEditLead}
            refreshToken={proposalRefresh}
          />
        </div>
      );
    case 'intel-assistant':
      return (
        <div className="flex h-full min-h-0 min-w-0 flex-col">
          <SalesAssistantPage />
        </div>
      );
    default:
      return null;
  }
}
