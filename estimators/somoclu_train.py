# -*- coding: utf-8 -*-
"""
The module contains the Somoclu class that trains and visualizes
self-organizing maps and emergent self-organizing maps.

http://peterwittek.github.io/somoclu/

Created on Sun July 26 15:07:47 2015

@author: Peter Wittek
"""
from __future__ import division, print_function
import numpy as np
import matplotlib.cm as cm
import matplotlib.pyplot as plt
import matplotlib.collections as mcoll

from .somoclu_wrap import train as wrap_train


class Somoclu(object):
    """Class for training and visualizing a self-organizing map.

    :param n_columns: The number of columns in the map.
    :type n_columns: int.
    :param n_rows: The number of rows in the map.
    :type n_rows: int.
    :param initialcodebook: Optional parameter to start the training with a
                            given codebook.
    :type initialcodebook: 2D numpy.array of float32.
    :param kerneltype: Optional parameter to specify which kernel to use:

                           * 0: dense CPU kernel (default)
                           * 1: dense GPU kernel (if compiled with it)
    :type kerneltype: int.
    :param maptype: Optional parameter to specify the map topology:
                           * "planar": Planar map (default)
                           * "toroid": Toroid map
    :type maptype: str.
    :param gridtype: Optional parameter to specify the grid form of the nodes:
                           * "rectangular": rectangular neurons (default)
                           * "hexagonal": hexagonal neurons
    :type gridtype: str.
    :param compactsupport: Optional parameter to cut off map updates beyond the
                           training radius. Default: False.
    :type compactsupport: bool.
    """

    def __init__(self, n_columns, n_rows, initialcodebook=None,
                 kerneltype=0, maptype="planar", gridtype="rectangular",
                 compactsupport=False):
        """Constructor for the class.
        """
        self._n_columns, self._n_rows = n_columns, n_rows
        self._kernel_type = kerneltype
        self._map_type = maptype
        self._grid_type = gridtype
        self._compact_support = compactsupport
        self._check_parameters()
        self.bmus = None
        self.umatrix = np.zeros(n_columns * n_rows, dtype=np.float32)
        self.codebook = initialcodebook
        self.n_vectors = 0
        self.n_dim = 0
        self.labels = None
        # self._data = None
        # if data is not None:
        #     self.update_data(data)

    def train(self, X, y=None, epochs=10, radius0=0, radiusN=1, radiuscooling="linear",
              scale0=0.1, scaleN=0.01, scalecooling="linear"):
        """Train the map on the current data in the Somoclu object.

        :param X: Obligatory parameter to provide training data.
        :type X: 2D numpy.array of float32.
        :param y: Optional parameter providing data labels for supervised learning
        :type y: list of arrays
        :param epochs: The number of epochs to train the map for.
        :type epochs: int.
        :param radius0: The initial radius on the map where the update happens
                        around a best matching unit. Default value of 0 will
                        trigger a value of min(n_columns, n_rows)/2.
        :type radius0: int.
        :param radiusN: The radius on the map where the update happens around a
                        best matching unit in the final epoch. Default: 1.
        :type radiusN: int.
        :param radiuscooling: The cooling strategy between radius0 and radiusN:
                                   * "linear": Linear interpolation (default)
                                   * "exponential": Exponential decay
        :param scale0: The initial learning scale. Default value: 0.1.
        :type scale0: int.
        :param scaleN: The learning scale in the final epoch. Default: 0.01.
        :type scaleN: int.
        :param scalecooling: The cooling strategy between scale0 and scaleN:
                                   * "linear": Linear interpolation (default)
                                   * "exponential": Exponential decay
        :type scalecooling: str.
        """
        _check_cooling_parameters(radiuscooling, scalecooling)
        if X is None:
            raise Exception("No data was provided!")
        else:
            X = np.array(X).astype(np.float32)
            self.n_vectors, self.n_dim = X.shape
            self.bmus = np.zeros(self.n_vectors * 2, dtype=np.intc)

        self._init_codebook()
        self.umatrix.shape = (self._n_rows * self._n_columns,)
        wrap_train(np.ravel(X), epochs, self._n_columns, self._n_rows,
                   self.n_dim, self.n_vectors, radius0, radiusN,
                   radiuscooling, scale0, scaleN, scalecooling,
                   self._kernel_type, self._map_type, self._grid_type,
                   self._compact_support, self.codebook, self.bmus,
                   self.umatrix)
        self.umatrix.shape = (self._n_rows, self._n_columns)
        self.bmus.shape = (self.n_vectors, 2)
        self.codebook.shape = (self._n_rows, self._n_columns, self.n_dim)

        if y is not None:
            self.label(X, np.array(y, dtype=int))

    def predict(self, x):

        bmu_ = np.linalg.norm(self.codebook - x, axis=2).argmin()
        return self.labels[divmod(bmu_, self.umatrix.shape[1])]

    def label(self, X, y):
        cls = np.unique(y)

        labels_ = np.zeros(self.umatrix.shape, dtype=int)
        if len(cls) == 2:
            labels_continuous_ = np.zeros(self.umatrix.shape, dtype=np.float32)
        for i in range(self.umatrix.shape[0]):
            for j in range(self.umatrix.shape[1]):
                # ATTENTION: either I am stupid here or the elements of self.bmus have wrong index order!
                #            -> using [i, i] instead of [i, i]
                cls_best_matching = y[np.where([np.array_equal(v, [j, i]) for v in self.bmus])[0]]
                cls_freq = [sum(cls_best_matching == c) for c in cls]
                max_cls_freq = max(cls_freq)
                if len(cls) == 2:
                    labels_continuous_[i, j] = np.mean(np.linalg.norm((X[y == cls[0]] - self.codebook[i, j]), axis=1))-\
                                               np.mean(np.linalg.norm((X[y == cls[1]] - self.codebook[i, j]), axis=1))

                if cls_freq.count(max_cls_freq) > 1:
                    distances = np.linalg.norm((X - self.codebook[i, j]), axis=1)
                    cls_ = cls[np.array(cls_freq) == max_cls_freq]
                    ind_winning_cls = np.array([np.median(distances[y == c]) for c in cls_]).argmin()
                    labels_[i, j] = cls_[ind_winning_cls]
                else:
                    ind_winning_cls = cls_freq.index(max_cls_freq)
                    labels_[i, j] = cls[ind_winning_cls]
        self.labels = labels_
        if len(cls) == 2:
            self.labels_continuous = labels_continuous_

    def load_bmus(self, filename):
        """Load the best matching units from a file to the Somoclu object.

        :param filename: The name of the file.
        :type filename: str.
        """
        self.bmus = np.loadtxt(filename, comments='%')
        if self.n_vectors != 0 and len(self.bmus) != self.n_vectors:
            raise Exception("The number of best matching units does not match"
                            "the number of data instances")
        else:
            self.n_vectors = len(self.bmus)
        if max(self.bmus[:, 1]) > self._n_columns - 1 or \
                        max(self.bmus[:, 2]) > self._n_rows - 1:
            raise Exception("The dimensions of the best matching units do not"
                            "match that of the map")

    def load_umatrix(self, filename):
        """Load the umatrix from a file to the Somoclu object.

        :param filename: The name of the file.
        :type filename: str.
        """

        self.umatrix = np.loadtxt(filename, comments='%')
        if self.umatrix.shape != (self._n_columns, self._n_rows):
            raise Exception("The dimensions of the U-matrix do not "
                            "match that of the map")

    def load_codebook(self, filename):
        """Load the codebook from a file to the Somoclu object.

        :param filename: The name of the file.
        :type filename: str.
        """
        self.codebook = np.loadtxt(filename, comments='%')
        if self.n_dim == 0:
            self.n_dim = self.codebook.shape[1]
        if self.codebook.shape != (self._n_rows * self._n_columns,
                                   self.n_dim):
            raise Exception("The dimensions of the codebook do not "
                            "match that of the map")
        self.codebook.shape = (self._n_rows, self._n_columns, self.n_dim)

    def view_component_planes(self, dimensions=None, figsize=None,
                              colormap=cm.Spectral_r, colorbar=False,
                              bestmatches=False, bestmatchcolors=None,
                              labels=None, zoom=None, filename=None):
        """Observe the component planes in the codebook of the SOM.

        :param dimensions: Optional parameter to specify along which dimension
                           or dimensions should the plotting happen. By
                           default, each dimension is plotted in a sequence of
                           plots.
        :type dimension: int or list of int.
        :param figsize: Optional parameter to specify the size of the figure.
        :type figsize: (int, int)
        :param colormap: Optional parameter to specify the color map to be
                         used.
        :type colormap: matplotlib.colors.Colormap
        :param colorbar: Optional parameter to include a colormap as legend.
        :type colorbar: bool.
        :param bestmatches: Optional parameter to plot best matching units.
        :type bestmatches: bool.
        :param bestmatchcolors: Optional parameter to specify the color of each
                                best matching unit.
        :type bestmatchcolors: list of int.
        :param labels: Optional parameter to specify the label of each point.
        :type labels: list of str.
        :param zoom: Optional parameter to zoom into a region on the map. The
                     first two coordinates of the tuple are the row limits, the
                     second tuple contains the column limits.
        :type zoom: ((int, int), (int, int))
        :param filename: If specified, the plot will not be shown but saved to
                         this file.
        :type filename: str.
        """
        if self.codebook is None:
            raise Exception("The codebook is not available. Either train a map"
                            " or load a codebook from a file")
        if dimensions is None:
            dimensions = range(self.n_dim)
        if not type(dimensions) == list:
            dimensions = [dimensions]
        for i in dimensions:
            self._view_matrix(self.codebook[:, :, i], figsize, colormap,
                              colorbar, bestmatches, bestmatchcolors, labels,
                              zoom, filename, title='Component plane %g' % i)

    def view_continuous_labels(self, figsize=None, colormap=cm.Spectral_r,
                               colorbar=False, bestmatches=False, bestmatchcolors=None,
                               labels=None, zoom=None, filename=None):
        """Plot the U-matrix of the trained map.

        :param figsize: Optional parameter to specify the size of the figure.
        :type figsize: (int, int)
        :param colormap: Optional parameter to specify the color map to be
                         used.
        :type colormap: matplotlib.colors.Colormap
        :param colorbar: Optional parameter to include a colormap as legend.
        :type colorbar: bool.
        :param bestmatches: Optional parameter to plot best matching units.
        :type bestmatches: bool.
        :param bestmatchcolors: Optional parameter to specify the color of each
                                best matching unit.
        :type bestmatchcolors: list of int.
        :param labels: Optional parameter to specify the label of each point.
        :type labels: list of str.
        :param zoom: Optional parameter to zoom into a region on the map. The
                     first two coordinates of the tuple are the row limits, the
                     second tuple contains the column limits.
        :type zoom: ((int, int), (int, int))
        :param filename: If specified, the plot will not be shown but saved to
                         this file.
        :type filename: str.
        """
        if not hasattr(self, 'labels_continuous') or self.labels_continuous is None:
            raise Exception("Continous labels are not available. Sure it's a"
                            " two-class problem?")
        self._view_matrix(self.labels_continuous, figsize, colormap, colorbar,
                          bestmatches, bestmatchcolors, labels, zoom, filename, title=' Label Matrix')

    def view_umatrix(self, figsize=None, colormap=cm.Spectral_r,
                     colorbar=False, bestmatches=False, bestmatchcolors=None,
                     labels=None, zoom=None, filename=None):
        """Plot the U-matrix of the trained map.

        :param figsize: Optional parameter to specify the size of the figure.
        :type figsize: (int, int)
        :param colormap: Optional parameter to specify the color map to be
                         used.
        :type colormap: matplotlib.colors.Colormap
        :param colorbar: Optional parameter to include a colormap as legend.
        :type colorbar: bool.
        :param bestmatches: Optional parameter to plot best matching units.
        :type bestmatches: bool.
        :param bestmatchcolors: Optional parameter to specify the color of each
                                best matching unit.
        :type bestmatchcolors: list of int.
        :param labels: Optional parameter to specify the label of each point.
        :type labels: list of str.
        :param zoom: Optional parameter to zoom into a region on the map. The
                     first two coordinates of the tuple are the row limits, the
                     second tuple contains the column limits.
        :type zoom: ((int, int), (int, int))
        :param filename: If specified, the plot will not be shown but saved to
                         this file.
        :type filename: str.
        """
        if self.umatrix is None:
            raise Exception("The U-matrix is not available. Either train a map"
                            " or load a U-matrix from a file")
        self._view_matrix(self.umatrix, figsize, colormap, colorbar,
                          bestmatches, bestmatchcolors, labels, zoom, filename, title='U-Matrix')

    def _view_matrix(self, matrix, figsize, colormap, colorbar, bestmatches,
                     bestmatchcolors, labels, zoom, filename, title=None):
        """Internal function to plot a map with best matching units and labels.
        """
        if zoom is None:
            zoom = ((0, self._n_rows), (0, self._n_columns))
        if figsize is None:
            figsize = (8, 8 / float(zoom[1][1] / zoom[0][1]))
        fig = plt.figure(figsize=figsize)
        if self._grid_type == "hexagonal":
            offsets = _hexplot(matrix[zoom[0][0]:zoom[0][1],
                               zoom[1][0]:zoom[1][1]], fig, colormap)
            filtered_bmus = self.filter_array(self.bmus, zoom)
            filtered_bmus[:, 0] = filtered_bmus[:, 0] - zoom[1][0]
            filtered_bmus[:, 1] = filtered_bmus[:, 1] - zoom[0][0]
            bmu_coords = np.zeros(filtered_bmus.shape)
            for i, (row, col) in enumerate(filtered_bmus):
                bmu_coords[i] = offsets[col * zoom[1][1] + row]
        else:
            plt.imshow(matrix[zoom[0][0]:zoom[0][1], zoom[1][0]:zoom[1][1]],
                       aspect='auto')
            plt.set_cmap(colormap)
            bmu_coords = self.filter_array(self.bmus, zoom)
            bmu_coords[:, 0] = bmu_coords[:, 0] - zoom[1][0]
            bmu_coords[:, 1] = bmu_coords[:, 1] - zoom[0][0]
        if colorbar:
            cmap = cm.ScalarMappable(cmap=colormap)
            cmap.set_array(matrix)
            # plt.colorbar(cmap, orientation='horizontal', shrink=0.5)
            plt.colorbar(cmap, orientation='vertical', shrink=1)

        if bestmatches:
            if bestmatchcolors is None:
                colors = "white"
            else:
                colors = self.filter_array(bestmatchcolors, zoom)
            plt.scatter(bmu_coords[:, 0], bmu_coords[:, 1], c=colors)

        if labels is not None:
            for label, col, row in zip(self.filter_array(labels, zoom),
                                       bmu_coords[:, 0], bmu_coords[:, 1]):
                if label is not None:
                    plt.annotate(label, xy=(col, row), xytext=(10, -5), textcoords='offset points',
                                 ha='left', va='bottom', bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.8))
        elif self.labels is not None:
            for row in range(self.umatrix.shape[0]):
                for col in range(self.umatrix.shape[1]):
                    plt.annotate(self.labels[row, col], xy=(col, row), xytext=(10, -5), textcoords='offset points',
                                 ha='left', va='bottom', bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.8))
        plt.axis('off')
        if title is not None:
            plt.title(title)
        if filename is not None:
            plt.savefig(filename)
        else:
            plt.show()
        return plt

    def filter_array(self, a, zoom):
        filtered_array = []
        for index, bmu in enumerate(self.bmus):
            if bmu[0] >= zoom[1][0] and bmu[0] < zoom[1][1] and \
                            bmu[1] >= zoom[0][0] and bmu[1] < zoom[0][1]:
                filtered_array.append(a[index])
        return np.array(filtered_array)

    def _check_parameters(self):
        """Internal function to verify the basic parameters of the SOM.
        """
        if self._map_type != "planar" and self._map_type != "toroid":
            raise Exception("Invalid parameter for _map_type: " +
                            self._map_type)
        if self._grid_type != "rectangular" and self._grid_type != "hexagonal":
            raise Exception("Invalid parameter for _grid_type: " +
                            self._grid_type)
        if self._kernel_type != 0 and self._kernel_type != 1:
            raise Exception("Invalid parameter for kernelTye: " +
                            self._kernel_type)

    def _init_codebook(self):
        """Internal function to set the codebook or to indicate it to the alpha++
        code that it should be randomly initialized.
        """
        codebook_size = self._n_columns * self._n_rows * self.n_dim
        if self.codebook is None:
            self.codebook = np.zeros(codebook_size, dtype=np.float32)
            self.codebook[0:2] = [1000, 2000]
        elif self.codebook.size != codebook_size:
            raise Exception("Invalid size for initial codebook")
        else:
            if self.codebook.dtype != np.float32:
                print("Warning: initialcodebook was not float32. A 32-bit "
                      "copy was made")
                self.codebook = np.float32(self.codebook)
        self.codebook.shape = (codebook_size,)


def _check_cooling_parameters(radiuscooling, scalecooling):
    """Helper function to verify the cooling parameters of the training.
    """
    if radiuscooling != "linear" and radiuscooling != "exponential":
        raise Exception("Invalid parameter for radiuscooling: " +
                        radiuscooling)
    if scalecooling != "linear" and scalecooling != "exponential":
        raise Exception("Invalid parameter for scalecooling: " +
                        scalecooling)


def _hexplot(matrix, fig, colormap):
    """Internal function to plot a hexagonal map.
    """
    umatrix_min = matrix.min()
    umatrix_max = matrix.max()
    n_rows, n_columns = matrix.shape
    cmap = plt.get_cmap(colormap)
    offsets = np.zeros((n_columns * n_rows, 2))
    facecolors = []
    for row in range(n_rows):
        for col in range(n_columns):
            if row % 2 == 0:
                offsets[row * n_columns + col] = [col + 0.5, 2 * n_rows - 2 * row]
                facecolors.append(cmap((matrix[row, col] - umatrix_min) /
                                       (umatrix_max) * 255))
            else:
                offsets[row * n_columns + col] = [col, 2 * n_rows - 2 * row]
                facecolors.append(cmap((matrix[row, col] - umatrix_min) /
                                       (umatrix_max) * 255))
    polygon = np.zeros((6, 2), float)
    polygon[:, 0] = 1.1 * np.array([0.5, 0.5, 0.0, -0.5, -0.5, 0.0])
    polygon[:, 1] = 1.1 * np.array([-np.sqrt(3) / 6, np.sqrt(3) / 6,
                                    np.sqrt(3) / 2 + np.sqrt(3) / 6,
                                    np.sqrt(3) / 6, -np.sqrt(3) / 6,
                                    -np.sqrt(3) / 2 - np.sqrt(3) / 6])
    polygons = np.expand_dims(polygon, 0) + np.expand_dims(offsets, 1)
    ax = fig.gca()
    collection = mcoll.PolyCollection(
        polygons,
        offsets=offsets,
        facecolors=facecolors,
        edgecolors=facecolors,
        linewidths=1.0,
        offset_position="data")
    ax.add_collection(collection, autolim=False)
    corners = ((-0.5, -0.5), (n_columns + 0.5, 2 * n_rows + 0.5))
    ax.update_datalim(corners)
    ax.autoscale_view(tight=True)
    return offsets
