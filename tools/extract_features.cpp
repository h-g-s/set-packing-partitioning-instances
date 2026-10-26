// SPDX-License-Identifier: EPL-2.0
#include "CbcHeuristicSppGrasp.hpp"
#include "OsiClpSolverInterface.hpp"
#include "OsiFeatures.hpp"
#include <iomanip>
#include <iostream>
#include <vector>

int main(int argc, char **argv)
{
  if (argc != 2) {
    std::cerr << "usage: extract_features instance.mps.gz\n";
    return 2;
  }
  OsiClpSolverInterface si;
  si.messageHandler()->setLogLevel(0);
  si.getModelPtr()->setLogLevel(0);
  if (si.readMps(argv[1])) {
    std::cerr << "cannot read " << argv[1] << "\n";
    return 1;
  }
  std::vector<double> features(OsiFeatures::n);
  OsiFeatures::compute(features.data(), &si);
  const CoinPackedMatrix *matrix = si.getMatrixByRow();
  const int *lengths = matrix->getVectorLengths();
  const CoinBigIndex *starts = matrix->getVectorStarts();
  const double *elements = matrix->getElements();
  int partition = 0, packing = 0, other = 0;
  bool binary = true;
  for (int j = 0; j < si.getNumCols(); ++j)
    binary = binary && si.isBinary(j);
  for (int i = 0; i < si.getNumRows(); ++i) {
    bool unit = lengths[i] > 0;
    for (CoinBigIndex k = starts[i]; k < starts[i] + lengths[i]; ++k)
      unit = unit && elements[k] == 1.0;
    if (unit && si.getRowUpper()[i] == 1.0 && si.getRowLower()[i] == 1.0)
      ++partition;
    else if (unit && si.getRowUpper()[i] == 1.0
             && si.getRowLower()[i] <= -si.getInfinity())
      ++packing;
    else
      ++other;
  }
  CbcSppGrasp grasp;
  const bool loaded = grasp.load(si);
  const bool eligible = loaded && !grasp.tooRestricted() && grasp.trivialSolutionExists();
  for (int i = 0; i < OsiFeatures::n; ++i)
    std::cout << OsiFeatures::name(i) << '\t';
  std::cout << "strict_partition\tstrict_packing\tstrict_other\tstrict_binary"
               "\tsense\tspp_loaded\tspp_partition\tspp_slack_rows\tspp_native_eligible\n";
  std::cout << std::setprecision(17);
  for (double value : features)
    std::cout << value << '\t';
  std::cout << partition << '\t' << packing << '\t' << other << '\t' << binary << '\t'
            << (si.getObjSense() > 0 ? "min" : "max") << '\t' << loaded << '\t'
            << (loaded ? grasp.numberPartitioningRows() : 0) << '\t'
            << (loaded ? grasp.numberSlackRows() : 0) << '\t' << eligible << '\n';
}
